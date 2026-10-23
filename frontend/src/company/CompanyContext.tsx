import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import type { components } from '../api/schema';

type Membership = components['schemas']['MeResponse']['companies'][number];
type Selection = {
  companyId: string | null;
  membership: Membership | undefined;
  setCompanyId: (id: string | null) => void;
};

const CompanyContext = createContext<Selection | null>(null);

export function CompanyProvider({ companies, children }: { companies: Membership[]; children: ReactNode }) {
  const [selectedId, setCompanyId] = useState<string | null>(null);
  const membership = companies.find(({ company }) => company.id === selectedId) ?? companies[0];
  return <CompanyContext.Provider value={{ companyId: membership?.company.id ?? null, membership, setCompanyId }}>{children}</CompanyContext.Provider>;
}

export function useCompany() {
  const value = useContext(CompanyContext);
  if (!value) throw new Error('Компания не выбрана: нужен CompanyProvider.');
  return value;
}
