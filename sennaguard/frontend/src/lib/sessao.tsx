import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, type Eu } from './api'

type Sessao = {
  eu: Eu | null
  carregando: boolean
  entrar: (email: string, senha: string) => Promise<void>
  sair: () => Promise<void>
  pode: (permissao: string) => boolean
  recarregar: () => Promise<void>
}

const Ctx = createContext<Sessao>(null!)
export const useSessao = () => useContext(Ctx)

export function ProvedorSessao({ children }: { children: ReactNode }) {
  const [eu, setEu] = useState<Eu | null>(null)
  const [carregando, setCarregando] = useState(true)

  useEffect(() => {
    api<Eu>('/api/eu').then(setEu).catch(() => setEu(null)).finally(() => setCarregando(false))
    const expirou = () => setEu(null)
    window.addEventListener('sg:sessao-expirou', expirou)
    return () => window.removeEventListener('sg:sessao-expirou', expirou)
  }, [])

  const entrar = useCallback(async (email: string, senha: string) => {
    setEu(await api<Eu>('/api/login', { method: 'POST', body: JSON.stringify({ email, senha }) }))
  }, [])
  const sair = useCallback(async () => {
    await api('/api/logout', { method: 'POST' }).catch(() => {})
    setEu(null)
  }, [])
  const pode = useCallback((p: string) => !!eu?.permissoes.includes(p), [eu])
  const recarregar = useCallback(async () => { setEu(await api<Eu>('/api/eu')) }, [])

  return <Ctx.Provider value={{ eu, carregando, entrar, sair, pode, recarregar }}>{children}</Ctx.Provider>
}
