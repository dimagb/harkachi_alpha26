import { Button, Container, Paper, PasswordInput, Stack, Text, TextInput, Title } from '@mantine/core';
import { useState, type FormEvent } from 'react';
import { api, fieldErrors } from './api/client';
import { setToken } from './auth/session';
import { demoAccounts } from './demoAccounts';

export default function Login() {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({});
    setLoading(true);
    try {
      const { data, error } = await api.POST('/auth/login', { body: { login, password } });
      if (error) setErrors(fieldErrors(error));
      else if (data) setToken(data.access_token);
    } catch {
      // The API client shows connection errors; the form stays available for retry.
    } finally {
      setLoading(false);
    }
  }

  return (
    <Container size={440} py="xl" mt="8vh">
      <Stack gap="xl">
        <div><Text fw={700} c="red">Кредитный кабинет</Text><Text size="sm" c="dimmed">Для вашего бизнеса</Text></div>
        <Paper withBorder p="xl" radius="md">
          <form onSubmit={submit}>
            <Stack>
              <Title order={1}>Вход</Title>
              <Text size="sm" c="dimmed">Войдите, чтобы работать с заявками на финансирование.</Text>
              <TextInput id="login" label="Логин" autoComplete="username" required value={login} onChange={(event) => setLogin(event.currentTarget.value)} error={errors.login} />
              <PasswordInput id="password" label="Пароль" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.currentTarget.value)} error={errors.password} visibilityToggleButtonProps={{ 'aria-label': 'Показать или скрыть пароль' }} />
              <Button type="submit" color="red" loading={loading} fullWidth>Войти</Button>
            </Stack>
          </form>
        </Paper>
        <Stack gap="xs">
          <Title order={2} size="h4">Демо-учётки</Title>
          <Text size="sm">Пароль для всех учёток: demo2026</Text>
          <Stack component="ul" aria-label="Демо-учётки" gap="xs" m={0} p={0} style={{ listStyle: 'none', minWidth: 0 }}>
            {demoAccounts.map((account) => (
              <li key={account.login} style={{ minWidth: 0 }}>
                <Paper
                  component="button" type="button" withBorder p="md" radius="md" w="100%"
                  style={{ textAlign: 'left', cursor: 'pointer', color: 'var(--cc-ink)', font: 'inherit' }}
                  onClick={() => {
                    setLogin(account.login);
                    setPassword('demo2026');
                    document.getElementById('login')?.closest('form')?.querySelector<HTMLButtonElement>('button[type="submit"]')?.focus();
                  }}
                >
                  <Text component="code" display="block" size="sm" fw={600} style={{ fontFamily: 'var(--mantine-font-family-monospace)', whiteSpace: 'nowrap' }}>{account.login}</Text>
                  <Text component="span" display="block" size="xs" c="var(--cc-ink-2)">{account.name}</Text>
                  <Text component="span" display="block" size="xs" c="var(--cc-ink-2)">{account.description}</Text>
                </Paper>
              </li>
            ))}
          </Stack>
          {import.meta.env.DEV && import.meta.env.VITE_USE_MSW === 'true' && <Text size="sm" c="dimmed">Работа без сервера.</Text>}
        </Stack>
      </Stack>
    </Container>
  );
}
