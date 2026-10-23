import { Button, Container, Paper, PasswordInput, Stack, Text, TextInput, Title } from '@mantine/core';
import { useState, type FormEvent } from 'react';
import { api, fieldErrors } from './api/client';
import { setToken } from './auth/session';

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
          <Text size="sm">ip_good — индивидуальный предприниматель</Text>
          <Text size="sm">ooo_load — руководитель компании</Text>
          <Text size="sm">underwriter — сотрудник банка</Text>
          {import.meta.env.DEV && import.meta.env.VITE_USE_MSW === 'true' && <Text size="sm" c="dimmed">Работа без сервера. Пароль для демо-учёток: demo2026.</Text>}
        </Stack>
      </Stack>
    </Container>
  );
}
