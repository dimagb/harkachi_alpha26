import { Button, Container, PasswordInput, Stack, Text, TextInput, Title } from '@mantine/core';
import { useState, type FormEvent } from 'react';
import { api, fieldErrors } from './api/client';
import { setToken } from './auth/session';
import { demoAccounts } from './demoAccounts';
import card from './screens/application/Card.module.css';
import css from './Login.module.css';
import shell from './App.module.css';
import alfaLogo from './assets/alfa-logo.svg';
import PrototypeFooter from './PrototypeFooter';

export default function Login() {
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({});
    setMessage('');
    setLoading(true);
    try {
      const { data, error, response } = await api.POST('/auth/login', { body: { login, password } });
      if (error) {
        setErrors(fieldErrors(error));
        if (response.status >= 500) setMessage('Не удалось войти. Попробуйте ещё раз.');
      }
      else if (data) setToken(data.access_token);
    } catch {
      setMessage('Не удалось войти. Проверьте соединение и попробуйте ещё раз.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={css.page}>
    <Container size={520} py="xl" className={css.content}>
      <Stack gap="xl">
        <div className={css.brand}><img className={shell.logo} src={`${alfaLogo}#svgView(viewBox(152,97,189,288))`} alt="Альфа-Банк" /><div><Text fw={600}>Кредитный кабинет</Text><Text size="sm" c="dimmed">Для вашего бизнеса</Text></div></div>
        <section className={card.card} aria-label="Вход в кабинет">
          <form onSubmit={submit}>
            <Stack>
              <h1 className={css.heading}>Вход</h1>
              <Text size="sm" c="dimmed">Войдите, чтобы работать с заявками на финансирование.</Text>
              <TextInput id="login" label="Логин" autoComplete="username" required value={login} onChange={(event) => setLogin(event.currentTarget.value)} error={errors.login} />
              <PasswordInput id="password" label="Пароль" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.currentTarget.value)} error={errors.password} visibilityToggleButtonProps={{ 'aria-label': 'Показать или скрыть пароль' }} />
              {message && <Text role="alert" c="stop">{message}</Text>}
              <Button type="submit" color="signal" className={card.cta} loading={loading} fullWidth>{message ? 'Повторить' : 'Войти'}</Button>
            </Stack>
          </form>
        </section>
        <section className={card.card} aria-label="Демо-учётки">
          <Title order={2} size="h4">Демо-учётки</Title>
          <Text size="sm">Пароль для всех учёток: demo2026</Text>
          <Stack component="ul" aria-label="Демо-учётки" gap="xs" m={0} p={0} style={{ listStyle: 'none', minWidth: 0 }}>
            {demoAccounts.map((account) => (
              <li key={account.login} style={{ minWidth: 0 }}>
                <button
                  type="button" className={css.account}
                  onClick={() => {
                    setLogin(account.login);
                    setPassword('demo2026');
                    setMessage('');
                    document.getElementById('login')?.closest('form')?.querySelector<HTMLButtonElement>('button[type="submit"]')?.focus();
                  }}
                >
                  <Text component="code" display="block" size="sm" fw={600} style={{ fontFamily: 'var(--mantine-font-family-monospace)', whiteSpace: 'nowrap' }}>{account.login}</Text>
                  <Text component="span" display="block" size="xs" c="var(--cc-ink-2)">{account.name}</Text>
                  <Text component="span" display="block" size="xs" c="var(--cc-ink-2)">{account.description}</Text>
                </button>
              </li>
            ))}
          </Stack>
          {import.meta.env.DEV && import.meta.env.VITE_USE_MSW === 'true' && <Text size="sm" c="dimmed">Работа без сервера.</Text>}
        </section>
      </Stack>
    </Container>
    <PrototypeFooter />
    </div>
  );
}
