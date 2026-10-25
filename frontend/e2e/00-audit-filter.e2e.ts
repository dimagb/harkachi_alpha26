import { execFile } from 'node:child_process';
import { createRequire } from 'node:module';
import process from 'node:process';
import { test, expect } from './helpers';

if (process.env.AUDIT_FILTER_PROBE === '1') {
  // Отдельный запуск: намеренные ошибки должны провалить и check(), и teardown аудита.
  test('00 audit — изолированная проверка ошибок', async ({ page, audit }, testInfo) => {
    await page.goto('/login');
    const messages = [
      'app error',
      `Loading the script '${new URL('/blocked.js', page.url())}' violates the following Content Security Policy directive: "script-src 'none'".`,
      'Loading the image \'http://blocked.invalid/image.png\' violates the following Content Security Policy directive: "img-src self".',
      'Loading the script \'not a URL\' violates the following Content Security Policy directive: "script-src self".',
    ];
    for (const message of messages) {
      await Promise.all([
        page.waitForEvent('console', { predicate: event => event.text() === message }),
        page.evaluate(text => console.error(text), message),
      ]);
      expect(() => audit.check()).toThrow(message.split(' violates the following')[0]);
    }
    testInfo.annotations.push({ type: 'audit-probe', description: 'Все четыре ошибки обнаружены check()' });
  });
} else {
  test('00 audit — чужой CSP-скрипт разрешён фильтром, ошибки приложения обнаружены', async ({ page, audit }, testInfo) => {
    await page.goto('/login');
    const [violation] = await Promise.all([
      page.waitForEvent('console', { predicate: message => message.type() === 'error' && message.text().includes('http://blocked.invalid/x.js') && message.text().includes('violates the following Content Security Policy') }),
      page.evaluate(() => {
        const script = document.createElement('script');
        script.src = 'http://blocked.invalid/x.js';
        document.head.append(script);
      }),
    ]);
    expect(violation.text()).toContain('Loading the script');
    expect(() => audit.check()).not.toThrow();

    // Запуск использует настоящую fixture из helpers.ts и отдельную папку артефактов.
    const probe = await new Promise<{ status: number; stdout: string; stderr: string }>((resolve, reject) => {
      execFile(process.execPath, [
        createRequire(import.meta.url).resolve('@playwright/test/cli'),
        'test', '00-audit-filter.e2e.ts', '--project=desktop', '--workers=1',
        '--reporter=json', '--output', testInfo.outputPath('probe'),
      ], {
        env: { ...process.env, AUDIT_FILTER_PROBE: '1', PLAYWRIGHT_JSON_OUTPUT_FILE: undefined, PLAYWRIGHT_JSON_OUTPUT_DIR: undefined, PLAYWRIGHT_JSON_OUTPUT_NAME: undefined },
        encoding: 'utf8', timeout: 120_000, windowsHide: true,
      }, (error, stdout, stderr) => {
        if (error && error.code !== 1) { reject(error); return; }
        resolve({ status: error ? 1 : 0, stdout, stderr });
      });
    });
    await testInfo.attach('audit-filter-probe', { body: probe.stdout ?? probe.stderr ?? '', contentType: 'application/json' });
    expect(probe.status).toBe(1);
    const report = JSON.parse(probe.stdout) as {
      errors: unknown[];
      stats: { unexpected: number; skipped: number };
      suites: { specs: { tests: { annotations: { type: string; description: string }[]; results: { errors: { message: string }[] }[] }[] }[] }[];
    };
    expect(report.errors).toEqual([]);
    expect(report.stats.unexpected).toBe(1);
    expect(report.stats.skipped).toBe(0);
    const result = report.suites[0].specs[0].tests[0];
    expect(result.annotations).toContainEqual({ type: 'audit-probe', description: 'Все четыре ошибки обнаружены check()' });
    expect(result.results[0].errors).toHaveLength(1);
    expect(result.results[0].errors[0].message).toContain('app error');
  });
}
