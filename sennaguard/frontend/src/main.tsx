import { StrictMode, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Shell from './components/Shell'
import { ProvedorSessao, useSessao } from './lib/sessao'
import Login from './pages/Login'
import Tv from './pages/Tv'
import Manutencoes from './pages/Manutencao'
import Backups from './pages/Backups'
import Testes from './pages/Testes'
import Conhecimento from './pages/Conhecimento'
import Visao from './pages/Visao'
import Alertas from './pages/Alertas'
import Chamados from './pages/Chamados'
import Equipamentos from './pages/Equipamentos'
import Usuarios from './pages/Usuarios'
import Perfil from './pages/Perfil'
import '@fontsource-variable/inter'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import './index.css'
import { aplicarTema } from './lib/tema'

aplicarTema()

/** Página só para quem tem a permissão; os outros voltam para a visão do enlace. */
function Exige({ permissao, children }: { permissao: string; children: ReactNode }) {
  return useSessao().pode(permissao) ? children : <Navigate to="/" replace />
}

function App() {
  const { eu, carregando } = useSessao()
  if (useLocation().pathname === '/tv') return <Tv />  // a TV entra pelo link fixo, sem login
  if (carregando) return null
  if (!eu) return <Login />
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Visao />} />
        <Route path="alertas" element={<Exige permissao="alertas"><Alertas /></Exige>} />
        <Route path="chamados" element={<Exige permissao="chamados"><Chamados /></Exige>} />
        <Route path="equipamentos" element={<Exige permissao="equipamentos"><Equipamentos /></Exige>} />
        <Route path="usuarios" element={<Exige permissao="usuarios"><Usuarios /></Exige>} />
        <Route path="manutencao" element={<Exige permissao="equipamentos"><Manutencoes /></Exige>} />
        <Route path="testes" element={<Exige permissao="testes"><Testes /></Exige>} />
        <Route path="backups" element={<Exige permissao="backups"><Backups /></Exige>} />
        <Route path="conhecimento" element={<Exige permissao="conhecimento"><Conhecimento /></Exige>} />
        <Route path="perfil" element={<Perfil />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '')}>
      <ProvedorSessao><App /></ProvedorSessao>
    </BrowserRouter>
  </StrictMode>,
)
