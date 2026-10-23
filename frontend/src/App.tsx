import { Badge, Container, Stack, Title } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { api } from './api/client';

export default function App() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: async ({ signal }) => {
      const { data, error } = await api.GET('/health', { signal });
      if (error || !data) throw new Error('API unavailable');
      return data;
    },
    retry: false,
  });
  const healthy = health.data?.status === 'ok' && !health.isError;

  return (
    <Container py="xl">
      <Stack align="flex-start">
        <Title order={1}>Кредитный кабинет — каркас</Title>
        <Badge color={healthy ? 'green' : 'red'} role="status">
          {healthy ? 'API: ok' : 'API: недоступен'}
        </Badge>
      </Stack>
    </Container>
  );
}

