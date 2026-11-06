import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import * as Menu from '@radix-ui/react-dropdown-menu'
import * as Dialog from '@radix-ui/react-dialog'
import { Bell, BookOpenText, ClockCounterClockwise, Compass, DotsThreeOutline, Flask, Wrench, CaretDoubleLeft, CaretDoubleRight, ChartLineUp, DotsThree, Lifebuoy, HardDrives, Moon, SignOut, Siren, Sun, TelegramLogo, Ticket, UserCircle, UsersThree } from '@phosphor-icons/react'
import { iniciarTempoReal, pararTempoReal, useApi, type Alerta, type ListaChamados } from '../lib/api'
import { alternarTema, temaAtual } from '../lib/tema'
import { situacao, type Manutencao } from '../pages/Manutencao'
import { ConectarTelegram } from '../pages/Perfil'
import { dataHora } from '../lib/fmt'
import { useSessao } from '../lib/sessao'
import Avatar from './Avatar'
import Modal from './Modal'
import Chat from './Chat'
import Tour from './Tour'

const NAV = [
  { para: '/', rotulo: 'Visão do enlace', curto: 'Visão', icone: ChartLineUp, permissao: 'visao' },
  { para: '/alertas', rotulo: 'Alertas e incidentes', curto: 'Alertas', icone: Siren, permissao: 'alertas' },
  { para: '/chamados', rotulo: 'Chamados', curto: 'Chamados', icone: Ticket, permissao: 'chamados' },
  { para: '/equipamentos', rotulo: 'Equipamentos', curto: 'Equip.', icone: HardDrives, permissao: 'equipamentos' },
  { para: '/manutencao', rotulo: 'Manutenção', curto: 'Manutenção', icone: Wrench, permissao: 'equipamentos' },
  { para: '/testes', rotulo: 'Testes de failover', curto: 'Testes', icone: Flask, permissao: 'testes' },
  { para: '/backups', rotulo: 'Backups', curto: 'Backups', icone: ClockCounterClockwise, permissao: 'backups' },
  { para: '/conhecimento', rotulo: 'Base de conhecimento', curto: 'Ajuda', icone: BookOpenText, permissao: 'conhecimento' },
  { para: '/usuarios', rotulo: 'Usuários', curto: 'Usuários', icone: UsersThree, permissao: 'usuarios' },
]
// Barra inferior do celular: 4 atalhos + "Mais" (o resto do menu fica na folha que sobe)
const ATALHOS_EQUIPE = ['/', '/alertas', '/chamados', '/equipamentos']
const ATALHOS_CLIENTE = ['/', '/chamados', '/conhecimento']
// O noc-senai-tcc é privado (o link dava 404 para o cliente); o README do SennaGuard é público
const AJUDA = 'https://github.com/MathZiraA/sennaguard#readme'
const item = 'flex h-8 cursor-default items-center gap-2 rounded-md px-2.5 text-tinta-2 outline-none data-[highlighted]:bg-white/5 data-[highlighted]:text-tinta'

export default function Shell() {
  const { eu, pode, sair } = useSessao()
  const [recolhida, setRecolhida] = useState(() => { try { return localStorage.getItem('sg:lateral') === '1' } catch { return false } })
  const { dados: alertas } = useApi<Alerta[]>(pode('alertas') ? '/api/alertas' : '', 10000, ['alertas'])
  // Para a equipe: chamados abertos pela Filial que ninguém assumiu ainda
  const { dados: ch } = useApi<ListaChamados>(pode('atender_chamado') ? '/api/chamados' : '', 60000, ['chamados'])
  const semDono = ch?.manuais.filter(c => c.status === 'aberto').length ?? 0
  const ativos = alertas?.filter(a => a.ativo && !a.reconhecido).length ?? 0
  // Faixa de manutenção: em andamento, ou começando nas próximas 24 h (aparece também para o cliente)
  const { dados: janelas } = useApi<Manutencao[]>('/api/manutencoes', 60000, ['manutencao'])
  const agora = Date.now() / 1000
  const janela = janelas?.find(m => !m.cancelada_em && m.inicio <= agora && agora < m.fim)
    ?? janelas?.find(m => !m.cancelada_em && m.inicio > agora && m.inicio - agora < 86400)
  const ponto: Record<string, string | null> = {
    '/alertas': ativos ? 'var(--color-desastre)' : null,
    '/chamados': semDono ? 'var(--color-media)' : null,
  }
  const alternar = () => { const r = !recolhida; setRecolhida(r); try { localStorage.setItem('sg:lateral', r ? '1' : '0') } catch { /* sem storage */ } }
  const [mais, setMais] = useState(false)
  const [ligandoTelegram, setLigandoTelegram] = useState(false)
  const [tour, setTour] = useState(false)
  const [tema, setTema] = useState(temaAtual)
  const local = useLocation()
  const ir = useNavigate()
  useEffect(() => { iniciarTempoReal(); return pararTempoReal }, [])
  useEffect(() => { setMais(false) }, [local.pathname])
  useEffect(() => { if (eu && !eu.tour_visto) setTour(true) }, [eu?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const permitidos = NAV.filter(n => pode(n.permissao))
  const atalhos = (eu?.papel === 'Cliente' ? ATALHOS_CLIENTE : ATALHOS_EQUIPE).map(p => permitidos.find(n => n.para === p)).filter(n => !!n)
  const resto = permitidos.filter(n => !atalhos.includes(n))

  const navegacao = (compacta: boolean) => (
    <nav className="flex flex-col gap-1" data-tour="nav">
      {permitidos.map(({ para, rotulo, icone: Icone }) => (
        <NavLink key={para} to={para} end title={compacta ? rotulo : undefined}
          className={({ isActive }) => `flex h-10 items-center gap-3 rounded-lg text-[13.5px] transition-colors duration-150 focus-visible:outline-offset-0 ${compacta ? 'justify-center' : 'px-3.5'} ${isActive ? 'bg-ativo text-tinta' : 'text-tinta-2 hover:bg-white/[0.04] hover:text-tinta'}`}>
          <span className="relative">
            <Icone size={19} weight="fill" />
            {compacta && ponto[para] && <span className="absolute -right-1 -top-0.5 size-1.5 rounded-full" style={{ background: ponto[para]! }} />}
          </span>
          {!compacta && <>{rotulo}{ponto[para] && <span className="size-1.5 rounded-full" style={{ background: ponto[para]! }} />}</>}
        </NavLink>
      ))}
    </nav>
  )

  return (
    <div className="flex min-h-screen">
      <aside className={`sticky top-0 hidden h-screen shrink-0 flex-col bg-lateral px-3.5 pb-5 pt-7 transition-[width] duration-200 md:flex ${recolhida ? 'w-[76px]' : 'w-[240px]'}`}>
        <div className={`mb-12 flex items-center ${recolhida ? 'justify-center' : 'justify-between pl-3'}`}>
          {!recolhida && <span className="text-[15px] font-medium tracking-[0.28em] text-tinta">SENNA<span className="text-fibra">G</span>UARD</span>}
          <button onClick={alternar} aria-label={recolhida ? 'Abrir menu' : 'Recolher menu'}
            className="grid size-7 place-items-center rounded-md text-tinta-2 transition-colors hover:bg-white/5 hover:text-tinta">
            {recolhida ? <CaretDoubleRight size={16} /> : <CaretDoubleLeft size={16} />}
          </button>
        </div>

        {navegacao(recolhida)}

        <div className="mt-auto flex flex-col gap-3">
          <a href={AJUDA} target="_blank" rel="noreferrer" title="Central de ajuda"
            className={`flex h-10 items-center gap-3 rounded-lg text-[13.5px] text-tinta-2 transition-colors hover:bg-white/[0.04] hover:text-tinta ${recolhida ? 'justify-center' : 'px-3.5'}`}>
            <Lifebuoy size={19} weight="fill" />{!recolhida && 'Central de ajuda'}
          </a>
          <div className="mx-1 h-px bg-fio-forte" />
          <Menu.Root>
            <Menu.Trigger data-tour="perfil" className={`flex items-center gap-2.5 rounded-lg py-1.5 text-left transition-colors hover:bg-white/[0.03] data-[state=open]:bg-white/[0.04] ${recolhida ? 'justify-center' : 'px-2'}`}>
              {eu && <Avatar id={eu.id} nome={eu.nome} foto={eu.foto} />}
              {!recolhida && <>
                <div className="min-w-0 flex-1 leading-tight">
                  <div className="truncate text-[12.5px] font-semibold">{eu?.nome}</div>
                  <div className="mt-0.5 text-[11px] text-tinta-3">{eu?.papel}</div>
                </div>
                <DotsThree size={20} weight="bold" className="text-tinta-2" />
              </>}
            </Menu.Trigger>
            <Menu.Portal>
              <Menu.Content side="top" align="start" sideOffset={6} className="z-50 w-[208px] rounded-lg border border-fio-forte bg-painel-alto p-1 text-[12.5px] shadow-2xl">
                <div className="truncate px-2.5 py-2 text-[11px] text-tinta-3">{eu?.email}</div>
                <Menu.Item onSelect={() => ir('/perfil')} className={item}><UserCircle size={14} weight="fill" />Meu perfil</Menu.Item>
                <Menu.Item onSelect={() => setLigandoTelegram(true)} className={item}>
                  <TelegramLogo size={14} weight="fill" />{eu?.telegram ? 'Telegram conectado' : 'Conectar Telegram'}
                  {eu?.telegram && <span className="ml-auto size-1.5 rounded-full bg-led" />}
                </Menu.Item>
                <Menu.Item onSelect={() => setTema(alternarTema())} className={item}>
                  {tema === 'claro' ? <><Moon size={14} />Tema escuro</> : <><Sun size={14} />Tema claro</>}
                </Menu.Item>
                <Menu.Item onSelect={() => setTour(true)} className={item}><Compass size={14} weight="fill" />Fazer o tour</Menu.Item>
                <Menu.Item onSelect={sair} className={`${item} data-[highlighted]:bg-desastre/10 data-[highlighted]:text-desastre`}><SignOut size={14} />Sair</Menu.Item>
              </Menu.Content>
            </Menu.Portal>
          </Menu.Root>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[64px] items-center gap-3 px-4 md:h-[76px] md:px-10">
          {/* Bloco da organização, como o "Amazon · Administration" da referência */}
          <div className="flex items-center gap-3">
            <div className="grid size-8 place-items-center rounded-full bg-white text-[14px] font-bold text-[#1c1b21] ring-1 ring-fio-forte">S</div>
            <div className="leading-tight">
              <div className="text-[12.5px] font-semibold text-tinta">SENAI</div>
              <div className="text-[12px] text-tinta-2">NOC Matriz · Filial</div>
            </div>
          </div>
          <div className="ml-auto flex items-center gap-1">
            {pode('alertas') && <NavLink to="/alertas" aria-label={`${ativos} alertas ativos`} data-tour="sino"
              className="relative grid size-9 place-items-center rounded-lg text-tinta transition-colors hover:bg-white/5">
              <Bell size={20} weight="fill" />
              {ativos > 0 && <span className="absolute right-2 top-1.5 size-2 rounded-full border-2 border-rack bg-desastre" />}
            </NavLink>}
            <NavLink to="/chamados" aria-label="Chamados" className="relative grid size-9 place-items-center rounded-lg text-tinta transition-colors hover:bg-white/5">
              <Ticket size={20} weight="fill" />
              {semDono > 0 && <span className="absolute right-1.5 top-1.5 size-2 rounded-full border-2 border-rack bg-media" />}
            </NavLink>
            {eu && <NavLink to="/perfil" aria-label="Meu perfil" className="ml-1 md:hidden"><Avatar id={eu.id} nome={eu.nome} foto={eu.foto} tamanho={30} /></NavLink>}
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 pb-[calc(88px+env(safe-area-inset-bottom))] pt-2 md:px-10 md:pb-8">
          {janela && (
            <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-[10px] border border-media/35 bg-media/10 px-5 py-3 text-[13px]">
              <Wrench size={17} weight="fill" className="text-media" />
              <b className="font-semibold">{situacao(janela).texto === 'Em andamento' ? 'Manutenção em andamento' : 'Manutenção programada'}:</b>
              <span>{janela.titulo}</span>
              <span className="num text-tinta-2">· {dataHora(janela.inicio)} até {dataHora(janela.fim)}</span>
              {janela.descricao && <span className="w-full text-[12px] text-tinta-2">{janela.descricao}</span>}
            </div>
          )}
          <Outlet />
        </main>
      </div>

      {/* Celular: barra inferior fixa com os atalhos do papel + "Mais" */}
      <nav data-tour="nav" className="fixed inset-x-0 bottom-0 z-30 flex border-t border-fio bg-lateral/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        {atalhos.map(({ para, curto, icone: Icone }) => (
          <NavLink key={para} to={para} end
            className={({ isActive }) => `relative flex h-[60px] flex-1 flex-col items-center justify-center gap-1 text-[10.5px] font-medium ${isActive ? 'text-fibra' : 'text-tinta-3'}`}>
            <span className="relative">
              <Icone size={22} weight="fill" />
              {ponto[para] && <span className="absolute -right-1 -top-0.5 size-2 rounded-full border-2 border-lateral" style={{ background: ponto[para]! }} />}
            </span>
            {curto}
          </NavLink>
        ))}
        <button onClick={() => setMais(true)} data-tour="perfil" className="flex h-[60px] flex-1 flex-col items-center justify-center gap-1 text-[10.5px] font-medium text-tinta-3">
          <DotsThreeOutline size={22} weight="fill" />Mais
        </button>
      </nav>
      <Dialog.Root open={mais} onOpenChange={setMais}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/55 md:hidden" />
          <Dialog.Content className="fixed inset-x-0 bottom-0 z-50 max-h-[85dvh] overflow-y-auto rounded-t-2xl border-t border-fio-forte bg-painel px-4 pb-[calc(16px+env(safe-area-inset-bottom))] pt-3 data-[state=open]:animate-[surge-chat_220ms_cubic-bezier(0.23,1,0.32,1)] md:hidden">
            <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-fio-forte" />
            <Dialog.Title className="sr-only">Mais opções</Dialog.Title>
            {eu && (
              <NavLink to="/perfil" className="mb-3 flex items-center gap-3 rounded-xl bg-painel-alto px-4 py-3">
                <Avatar id={eu.id} nome={eu.nome} foto={eu.foto} tamanho={40} />
                <div className="min-w-0 flex-1"><div className="truncate font-semibold">{eu.nome}</div><div className="text-[12px] text-tinta-3">{eu.papel} · Meu perfil</div></div>
              </NavLink>
            )}
            <div className="grid grid-cols-3 gap-2">
              {resto.map(({ para, curto, icone: Icone }) => (
                <NavLink key={para} to={para} className={({ isActive }) => `flex h-[72px] flex-col items-center justify-center gap-1.5 rounded-xl text-[11.5px] font-medium ${isActive ? 'bg-ativo text-tinta' : 'bg-painel-alto text-tinta-2'}`}>
                  <Icone size={22} weight="fill" />{curto}
                </NavLink>
              ))}
            </div>
            <div className="mt-3 flex flex-col">
              {[
                { rotulo: eu?.telegram ? 'Telegram conectado' : 'Conectar Telegram', icone: TelegramLogo, acao: () => { setMais(false); setLigandoTelegram(true) } },
                { rotulo: tema === 'claro' ? 'Tema escuro' : 'Tema claro', icone: tema === 'claro' ? Moon : Sun, acao: () => setTema(alternarTema()) },
                { rotulo: 'Fazer o tour', icone: Compass, acao: () => { setMais(false); setTour(true) } },
                { rotulo: 'Central de ajuda', icone: Lifebuoy, acao: () => window.open(AJUDA, '_blank', 'noreferrer') },
              ].map(({ rotulo, icone: Icone, acao }) => (
                <button key={rotulo} onClick={acao} className="flex h-12 items-center gap-3 border-b border-fio px-1 text-left text-tinta-2"><Icone size={19} weight="fill" />{rotulo}</button>
              ))}
              <button onClick={sair} className="flex h-12 items-center gap-3 px-1 text-left text-desastre"><SignOut size={19} />Sair</button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {pode('chat') && <Chat />}
      <Tour aberto={tour} onFim={() => setTour(false)} />
      <Modal aberto={ligandoTelegram} onClose={() => setLigandoTelegram(false)} titulo="Avisos no Telegram"
        descricao="Chamados novos, respostas e alertas chegam direto no seu Telegram. Escolha quais em Meu perfil.">
        <ConectarTelegram conectado={!!eu?.telegram} disponivel={!!eu?.telegram_disponivel} />
      </Modal>
    </div>
  )
}

/** Dois trilhos (fibra e rádio) ligando dois nós: o mesmo desenho do enlace, em miniatura. */
export function Marca() {
  return (
    <svg viewBox="0 0 28 28" className="size-7" aria-hidden>
      <rect width="28" height="28" rx="8" fill="var(--color-fibra)" fillOpacity=".14" />
      <path d="M7 11 H21" stroke="var(--color-fibra)" strokeWidth="2" strokeLinecap="round" />
      <path d="M7 17 H21" stroke="var(--color-radio)" strokeWidth="2" strokeLinecap="round" strokeDasharray="2 3" />
      <circle cx="7" cy="14" r="2.6" fill="var(--color-tinta)" />
      <circle cx="21" cy="14" r="2.6" fill="var(--color-tinta)" />
    </svg>
  )
}
