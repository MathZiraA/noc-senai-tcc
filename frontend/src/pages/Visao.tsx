import { useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import * as Menu from '@radix-ui/react-dropdown-menu'
import { ArrowDown, ArrowsClockwise, ArrowsOut, ArrowUp, CalendarBlank, CaretDown, CaretRight, CellSignalFull, CellSignalX, Cpu, DotsSixVertical, DownloadSimple, Eye, EyeSlash, FileText, LinkBreak, LinkSimple, MagnifyingGlassMinus, Plus, SlidersHorizontal, SquaresFour } from '@phosphor-icons/react'
import { api, useApi, type Alerta, type LinkWan, type ListaChamados, type Painel, type Ponto, type Visao as TVisao } from '../lib/api'
import { dataHora, desde, duracao, hora } from '../lib/fmt'
import { useSessao } from '../lib/sessao'
import Grafico, { faixasSemResposta, type Limite } from '../components/Grafico'
import { StatusChamado } from '../components/Atendimento'
import Modal from '../components/Modal'
import { Botao, Card, Carregando, Chip } from '../components/ui'

// Até 30 min: 1 ponto por segundo (sonda do servidor), para demonstrar queda e volta ao vivo
const CURTO = 0.5
const periodos = [
  { h: 5 / 60, r: 'Últimos 5 minutos' }, { h: 10 / 60, r: 'Últimos 10 minutos' }, { h: CURTO, r: 'Últimos 30 minutos' },
  { h: 1, r: 'Última hora' }, { h: 6, r: 'Últimas 6 horas' }, { h: 24, r: 'Últimas 24 horas' },
  { h: 168, r: 'Últimos 7 dias' }, { h: 720, r: 'Últimos 30 dias' },
]
type Recorte = { de: number; ate: number }

// "Atualizar a cada", como no Grafana. Automático = 1 s nos períodos curtos, 10 s nos demais, e na hora quando
// um enlace cai ou volta. Qualquer outro valor é seguido à risca: a tela só recarrega naquele ritmo.
const AUTOMATICO = -1
const ritmos = [
  { ms: AUTOMATICO, r: 'Automático' }, { ms: 0, r: 'Desligado' }, { ms: 1000, r: '1 s' }, { ms: 2000, r: '2 s' },
  { ms: 5000, r: '5 s' }, { ms: 10000, r: '10 s' }, { ms: 30000, r: '30 s' }, { ms: 60000, r: '1 min' }, { ms: 300000, r: '5 min' },
]
const lerRitmo = () => {
  try { const v = Number(localStorage.getItem('sg-atualizar')); return ritmos.some(r => r.ms === v) && localStorage.getItem('sg-atualizar') !== null ? v : AUTOMATICO }
  catch { return AUTOMATICO }
}

// Limites reais do projeto: troca automática da fibra em 30 ms (netwatch) e trigger do rádio em 50 ms;
// "Normal" = o que a bancada mediu em 16/10/2026.
const LIMITES: Record<'fibra' | 'radio', Limite[]> = {
  fibra: [{ valor: 30, rotulo: 'Crítico', tipo: 'critico' }, { valor: 0.6, rotulo: 'Normal', tipo: 'normal' }],
  radio: [{ valor: 50, rotulo: 'Crítico', tipo: 'critico' }, { valor: 6.4, rotulo: 'Normal', tipo: 'normal' }],
}

const CRITICO = ['Desastre', 'Alta']

/** Cartões da Visão. `total` ocupa a linha; `largo` e `estreito` dividem a linha na proporção do gráfico + lateral. */
const CARTOES: Record<string, { nome: string; tamanho: 'total' | 'largo' | 'estreito' }> = {
  contexto: { nome: 'Faixa do roteador', tamanho: 'total' },
  latencia: { nome: 'Latência', tamanho: 'largo' },
  alertas: { nome: 'Alertas', tamanho: 'estreito' },
  chamados: { nome: 'Seus chamados', tamanho: 'estreito' },
  trafego: { nome: 'Tráfego na Filial', tamanho: 'largo' },
  caminho: { nome: 'Caminho ativo', tamanho: 'estreito' },
  internet: { nome: 'Internet', tamanho: 'estreito' },
}
const LARGURA = { total: 'basis-full', largo: 'basis-[520px] grow-[10]', estreito: 'basis-[300px] grow' }

/** Ordem salva na conta + cartões novos que ainda não estavam nela, só os que o papel pode ver. */
function montar(painel: Painel | null, padrao: string[]): Painel {
  const ordem = [...(painel?.ordem ?? []).filter(c => padrao.includes(c)), ...padrao.filter(c => !painel?.ordem.includes(c))]
  return { ordem, ocultos: (painel?.ocultos ?? []).filter(c => padrao.includes(c)) }
}

/** Períodos prontos do relatório em PDF (segundos Unix). */
function relatorios() {
  const agora = Math.floor(Date.now() / 1000)
  const inicioMes = new Date(); inicioMes.setDate(1); inicioMes.setHours(0, 0, 0, 0)
  const mesPassado = new Date(inicioMes); mesPassado.setMonth(mesPassado.getMonth() - 1)
  const s = (d: Date) => Math.floor(d.getTime() / 1000)
  return [
    { rotulo: 'Últimas 24 horas', de: agora - 86400, ate: agora },
    { rotulo: 'Últimos 7 dias', de: agora - 7 * 86400, ate: agora },
    { rotulo: 'Este mês', de: s(inicioMes), ate: agora },
    { rotulo: `Mês passado (${mesPassado.toLocaleDateString('pt-BR', { month: 'long' })})`, de: s(mesPassado), ate: s(inicioMes) },
  ]
}

/** Nome curto do trigger, para a pílula do alerta (o equivalente ao "12°C" da referência). */
export function curto(nome: string) {
  const n = nome.toUpperCase()
  if (n.startsWith('FILIAL ISOLADA')) return 'Filial isolada'
  if (n.startsWith('PREVISÃO')) return 'Previsão rádio'
  if (n.includes('FIBRA') && n.includes('INSTÁVEL')) return 'Fibra instável'
  if (n.startsWith('LINK FIBRA')) return 'Fibra caiu'
  if (n.startsWith('LINK RÁDIO')) return 'Rádio caiu'
  if (n.includes('PERDA')) return 'Perda no rádio'
  if (n.includes('ACIMA DO NORMAL')) return 'Rádio lento'
  if (n.includes('LATÊNCIA ALTA')) return 'Latência alta'
  if (n.includes('SEM COMUNICAÇÃO')) return 'Failover lento'
  return nome.split(':')[0]
}

const itemMenu = 'flex h-8 cursor-default items-center rounded-md px-2.5 text-tinta-2 outline-none data-[highlighted]:bg-white/5 data-[highlighted]:text-tinta'

export default function Visao() {
  const [horas, setHoras] = useState(24)
  const [recorte, setRecorte] = useState<Recorte | null>(null) // zoom ou período personalizado
  const [escolhendo, setEscolhendo] = useState(false)
  const [enlace, setEnlace] = useState<'fibra' | 'radio'>('fibra')
  const [comLimites, setComLimites] = useState(true)
  const { pode, eu, recarregar } = useSessao()
  const interno = pode('alertas') // equipe do NOC; o cliente vê os próprios chamados no lugar dos alertas
  const padrao = ['contexto', 'latencia', interno ? 'alertas' : 'chamados', 'trafego', 'caminho', 'internet']
  const [rascunho, setRascunho] = useState<Painel | null>(null) // != null = editando o painel
  const [arrastando, setArrastando] = useState<string | null>(null)
  const painel = rascunho ?? montar(eu?.painel ?? null, padrao)

  const periodo = recorte ? `de=${recorte.de}&ate=${recorte.ate}` : `horas=${horas}`
  const curto = !recorte && horas <= CURTO
  const [ritmo, setRitmo] = useState(lerRitmo)
  const escolherRitmo = (ms: number) => { setRitmo(ms); try { localStorage.setItem('sg-atualizar', String(ms)) } catch { /* sem armazenamento: vale só nesta aba */ } }
  const auto = ritmo === AUTOMATICO
  // Automático: períodos curtos a cada 1 s, os demais a cada 10 s, e na hora pelo canal "visao" quando um enlace muda.
  // Ritmo escolhido: tudo nesta tela recarrega exatamente nele, sem recargas extras (zoom fixo não recarrega).
  const cada = (padrao: number) => (auto ? padrao : ritmo)
  const canais = (c: string[]) => (auto ? c : [])
  const ao_vivo = recorte ? 0 : cada(curto ? 1000 : 10000)
  const { dados: v } = useApi<TVisao>('/api/visao', cada(curto ? 2000 : 10000), canais(['visao']))
  const { dados: lat } = useApi<Ponto[]>(`/api/serie/latencia?${periodo}`, ao_vivo, recorte ? [] : canais(['visao']))
  const { dados: trf } = useApi<Ponto[]>(`/api/serie/trafego?${periodo}`, ao_vivo)
  const { dados: alertas } = useApi<Alerta[]>(interno ? '/api/alertas' : '', cada(10000), canais(['alertas']))
  const { dados: ch } = useApi<ListaChamados>(interno ? '' : '/api/chamados', cada(60000), canais(['chamados']))

  const baixar = (nome: string, linhas: string[]) => {
    const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(new Blob([linhas.join('\n')], { type: 'text/csv' })), download: nome })
    a.click()
  }
  const exportar = () => lat && baixar(`sennaguard-latencia-${recorte ? `${recorte.de}-${recorte.ate}` : `${horas}h`}.csv`,
    ['horario;latencia_fibra_ms;latencia_radio_ms', ...lat.map(p => `${new Date(p.t * 1000).toISOString()};${p.fibra ?? ''};${p.radio ?? ''}`)])
  const zoom = (de: number, ate: number) => setRecorte({ de: Math.floor(de), ate: Math.ceil(ate) })

  const ultimo = lat?.length ? lat[lat.length - 1] : null
  const atual = ultimo?.[enlace] ?? null
  const cor = enlace === 'fibra' ? 'var(--color-fibra)' : 'var(--color-radio)'
  const trafego = trf?.map(p => ({ t: p.t, mbps: p.fibra ?? p.radio }))
  const mbps = trafego?.length ? trafego[trafego.length - 1].mbps : null
  const media = trafego?.length ? trafego.reduce((s, p) => s + (p.mbps ?? 0), 0) / trafego.length : 0

  const conteudo: Record<string, ReactNode> = {
    contexto: v ? <Contexto v={v} interno={interno} /> : <Carregando />,
    latencia: (
      <Card className="h-full md:!px-9 md:!pt-7 !pb-5"
        titulo={enlace === 'fibra' ? 'Latência da fibra' : 'Latência do rádio'}
        extra={<Valor valor={atual == null ? 'sem resposta' : `${atual.toLocaleString('pt-BR')} ms`} erro={atual == null} cor={cor} quando={recorte ? undefined : ultimo?.t} />}
        acao={<div className="flex gap-1.5">
          <Chip ativo={enlace === 'fibra'} onClick={() => setEnlace('fibra')}>Fibra</Chip>
          <Chip ativo={enlace === 'radio'} onClick={() => setEnlace('radio')}>Rádio</Chip>
          <Chip ativo={comLimites} onClick={() => setComLimites(!comLimites)}><SlidersHorizontal />Limites</Chip>
        </div>}>
        {lat ? <Grafico dados={lat} serie={enlace} cor={cor} unidade="ms" altura={250} onZoom={zoom}
          limites={comLimites ? LIMITES[enlace] : []}
          faixas={faixasSemResposta(lat, enlace, enlace === 'fibra' ? 'Fibra fora' : 'Rádio fora')} />
          : <div className="h-[250px]" />}
      </Card>
    ),
    alertas: <CardAlertas alertas={alertas} baixar={baixar} />,
    chamados: <CardChamados ch={ch} />,
    internet: <CardInternet i={v?.internet} />,
    trafego: (
      <Card className="h-full md:!px-9 md:!pt-7 !pb-5" titulo="Tráfego na Filial"
        extra={<Valor valor={mbps == null ? '—' : `${mbps.toLocaleString('pt-BR', { maximumFractionDigits: mbps < 10 ? 2 : 0 })} Mbps`} cor="var(--color-fibra)" quando={recorte ? undefined : trf?.[trf.length - 1]?.t} />}>
        {trafego ? <Grafico dados={trafego} serie="mbps" cor="var(--color-fibra)" unidade="Mbps" altura={150} onZoom={zoom}
          limites={comLimites && media ? [{ valor: Math.round(media * 100) / 100, rotulo: 'Média', tipo: 'normal' }] : []} />
          : <div className="h-[150px]" />}
      </Card>
    ),
    caminho: lat && v ? <CardCaminho pontos={lat} v={v} alertas={alertas ?? []} /> : <Card className="h-full"><div className="h-[150px]" /></Card>,
  }

  const mover = (id: string, para: number) => {
    if (!rascunho) return
    const ordem = rascunho.ordem.filter(c => c !== id)
    ordem.splice(Math.max(0, Math.min(para, ordem.length)), 0, id)
    setRascunho({ ...rascunho, ordem })
  }
  const salvar = async () => {
    if (rascunho) await api('/api/eu/painel', { method: 'PUT', body: JSON.stringify(rascunho) })
    await recarregar(); setRascunho(null)
  }
  const restaurar = async () => { await api('/api/eu/painel', { method: 'DELETE' }); await recarregar(); setRascunho(null) }

  return (
    <div className="flex flex-col gap-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <h1 className="flex items-center gap-2.5 text-[22px] font-medium tracking-[-0.02em] text-titulo">
          Enlaces<CaretRight size={18} weight="bold" className="text-titulo" />Matriz ⇄ Filial
        </h1>
        {rascunho ? (
          <div className="flex flex-wrap gap-2.5">
            <Botao variante="contorno" onClick={restaurar}>Restaurar padrão</Botao>
            <Botao onClick={() => setRascunho(null)}>Cancelar</Botao>
            <Botao variante="primario" onClick={salvar}>Concluir</Botao>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2.5">
            {recorte && <Botao variante="contorno" onClick={() => setRecorte(null)}><MagnifyingGlassMinus />Voltar para {periodos.find(p => p.h === horas)?.r.toLowerCase()}</Botao>}
            <Menu.Root>
              <Menu.Trigger asChild><Botao variante="contorno" data-tour="periodo">
                {recorte ? <span className="num">{dataHora(recorte.de)} – {dataHora(recorte.ate)}</span> : periodos.find(p => p.h === horas)?.r}<CaretDown weight="fill" />
              </Botao></Menu.Trigger>
              <Menu.Portal>
                <Menu.Content align="end" sideOffset={6} className="z-50 min-w-48 rounded-lg border border-fio-forte bg-painel-alto p-1 text-[12.5px] shadow-2xl">
                  {periodos.map(p => (
                    <Menu.Item key={p.h} onSelect={() => { setHoras(p.h); setRecorte(null) }}
                      className={`${itemMenu} ${!recorte && p.h === horas ? '!text-fibra' : ''}`}>{p.r}</Menu.Item>
                  ))}
                  <div className="my-1 h-px bg-fio" />
                  <Menu.Item onSelect={() => setEscolhendo(true)} className={`${itemMenu} gap-2`}><CalendarBlank size={14} />Personalizado…</Menu.Item>
                </Menu.Content>
              </Menu.Portal>
            </Menu.Root>
            <Menu.Root>
              <Menu.Trigger asChild><Botao variante="contorno" title="Atualizar a cada">
                <ArrowsClockwise />{ritmos.find(r => r.ms === ritmo)?.r}<CaretDown weight="fill" />
              </Botao></Menu.Trigger>
              <Menu.Portal>
                <Menu.Content align="end" sideOffset={6} className="z-50 min-w-44 rounded-lg border border-fio-forte bg-painel-alto p-1 text-[12.5px] shadow-2xl">
                  <div className="px-2.5 pb-1 pt-1.5 text-[11px] text-tinta-3">Atualizar a cada</div>
                  {ritmos.map(r => (
                    <Menu.Item key={r.ms} onSelect={() => escolherRitmo(r.ms)}
                      className={`${itemMenu} ${r.ms === ritmo ? '!text-fibra' : ''}`}>{r.r}</Menu.Item>
                  ))}
                </Menu.Content>
              </Menu.Portal>
            </Menu.Root>
            <Menu.Root>
              <Menu.Trigger asChild><Botao><FileText />Exportar relatório</Botao></Menu.Trigger>
              <Menu.Portal>
                <Menu.Content align="end" sideOffset={6} className="z-50 min-w-56 rounded-lg border border-fio-forte bg-painel-alto p-1 text-[12.5px] shadow-2xl">
                  {pode('relatorios') && <>
                    <div className="px-2.5 pb-1 pt-1.5 text-[11px] text-tinta-3">Relatório de SLA (PDF)</div>
                    {relatorios().map(r => (
                      <Menu.Item key={r.rotulo} onSelect={() => window.open(`${import.meta.env.BASE_URL}api/relatorio.pdf?de=${r.de}&ate=${r.ate}`)} className={itemMenu}>{r.rotulo}</Menu.Item>
                    ))}
                    <div className="my-1 h-px bg-fio" />
                  </>}
                  <Menu.Item onSelect={exportar} className={itemMenu}>Latência do período (CSV)</Menu.Item>
                </Menu.Content>
              </Menu.Portal>
            </Menu.Root>
            <Botao variante="quieto" onClick={() => setRascunho(painel)} data-tour="editar-painel" aria-label="Editar painel" title="Editar painel"><SquaresFour weight="fill" /><span className="hidden sm:inline">Editar painel</span></Botao>
          </div>
        )}
      </div>

      {rascunho && <p className="-mt-2 text-[12px] text-tinta-3">Arraste os cartões pela alça (ou use as setas) e toque no olho para esconder. Fica salvo na sua conta.</p>}

      <div className="flex flex-wrap gap-3">
        {painel.ordem.filter(id => rascunho || !painel.ocultos.includes(id)).map((id, i) => {
          const oculto = painel.ocultos.includes(id)
          return (
            <div key={id} data-tour={id} className={`relative min-w-0 ${LARGURA[CARTOES[id].tamanho]} ${rascunho && oculto ? 'opacity-35' : ''} ${arrastando === id ? 'opacity-50' : ''}`}
              draggable={!!rascunho} onDragStart={e => { setArrastando(id); e.dataTransfer.effectAllowed = 'move' }} onDragEnd={() => setArrastando(null)}
              onDragOver={e => { if (rascunho && arrastando) e.preventDefault() }}
              onDrop={e => { e.preventDefault(); if (arrastando && arrastando !== id) mover(arrastando, rascunho!.ordem.indexOf(id)); setArrastando(null) }}>
              {conteudo[id]}
              {rascunho && (
                <div className="absolute inset-0 z-10 flex items-start justify-between gap-2 rounded-xl bg-rack/40 p-2 outline-2 outline-dashed outline-fibra/50">
                  <span className="flex cursor-grab items-center gap-1.5 rounded-md bg-painel-alto px-2 py-1 text-[12px] font-medium shadow active:cursor-grabbing">
                    <DotsSixVertical size={16} weight="bold" />{CARTOES[id].nome}{oculto && <span className="text-tinta-3">· escondido</span>}
                  </span>
                  <span className="flex gap-1 rounded-md bg-painel-alto p-0.5 shadow">
                    <BotaoIcone rotulo="Mover para antes" onClick={() => mover(id, i - 1)} desligado={i === 0}><ArrowUp /></BotaoIcone>
                    <BotaoIcone rotulo="Mover para depois" onClick={() => mover(id, i + 1)} desligado={i === painel.ordem.length - 1}><ArrowDown /></BotaoIcone>
                    <BotaoIcone rotulo={oculto ? 'Mostrar' : 'Esconder'} onClick={() => setRascunho({ ...rascunho, ocultos: oculto ? rascunho.ocultos.filter(c => c !== id) : [...rascunho.ocultos, id] })}>
                      {oculto ? <EyeSlash /> : <Eye />}
                    </BotaoIcone>
                  </span>
                </div>
              )}
            </div>
          )
        })}
        {!rascunho && painel.ordem.every(id => painel.ocultos.includes(id)) && (
          <p className="w-full rounded-xl border border-dashed border-fio py-10 text-center text-tinta-3">Todos os cartões estão escondidos. Use <b className="text-tinta-2">Editar painel</b> para mostrar.</p>
        )}
      </div>

      <Modal aberto={escolhendo} onClose={() => setEscolhendo(false)} titulo="Período personalizado" descricao="Até 31 dias. Dica: arrastar sobre o gráfico também dá zoom.">
        <EscolherPeriodo inicial={recorte} onEscolher={r => { setRecorte(r); setEscolhendo(false) }} />
      </Modal>
    </div>
  )
}

function BotaoIcone({ rotulo, onClick, desligado = false, children }: { rotulo: string; onClick: () => void; desligado?: boolean; children: ReactNode }) {
  return (
    <button type="button" aria-label={rotulo} title={rotulo} onClick={onClick} disabled={desligado}
      className="grid size-7 place-items-center rounded text-tinta-2 hover:bg-white/5 hover:text-tinta disabled:opacity-30 [&_svg]:size-4">{children}</button>
  )
}

/** datetime-local trabalha em hora local sem fuso: converte nos dois sentidos. */
const paraCampo = (t: number) => { const d = new Date(t * 1000); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16) }

function EscolherPeriodo({ inicial, onEscolher }: { inicial: Recorte | null; onEscolher: (r: Recorte) => void }) {
  const agora = Math.floor(Date.now() / 1000)
  const [de, setDe] = useState(paraCampo(inicial?.de ?? agora - 86400))
  const [ate, setAte] = useState(paraCampo(inicial?.ate ?? agora))
  const [erro, setErro] = useState('')
  const campo = 'h-9 w-full rounded-lg border border-fio bg-fenda px-3 text-tinta focus:border-fibra/60 focus:outline-none'
  const enviar = (e: FormEvent) => {
    e.preventDefault()
    const r = { de: Math.floor(new Date(de).getTime() / 1000), ate: Math.floor(new Date(ate).getTime() / 1000) }
    if (!(r.ate > r.de)) return setErro('O fim precisa ser depois do início.')
    if (r.ate - r.de > 31 * 86400) return setErro('O período pode ter no máximo 31 dias.')
    if (r.de > agora) return setErro('O início não pode estar no futuro.')
    onEscolher({ de: r.de, ate: Math.min(r.ate, agora) })
  }
  return (
    <form onSubmit={enviar} className="flex flex-col gap-3.5">
      <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">Início
        <input type="datetime-local" required value={de} max={paraCampo(agora)} onChange={e => setDe(e.target.value)} className={campo} /></label>
      <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">Fim
        <input type="datetime-local" required value={ate} max={paraCampo(agora)} onChange={e => setAte(e.target.value)} className={campo} /></label>
      {erro && <p className="text-[12px] text-desastre">{erro}</p>}
      <Botao type="submit" variante="primario" className="self-end">Aplicar</Botao>
    </form>
  )
}

function Valor({ valor, cor, quando, erro = false }: { valor: string; cor: string; quando?: number; erro?: boolean }) {
  return (
    <span className="flex items-baseline gap-2">
      <span className="num text-[17px] font-semibold" style={{ color: erro ? 'var(--color-desastre)' : cor }}>{valor}</span>
      {quando && <span className="text-[10.5px] text-tinta-3">há {desde(quando)}</span>}
    </span>
  )
}

/** Faixa do host monitorado, com divisores, como a do sensor na referência. */
function Contexto({ v, interno }: { v: TVisao; interno: boolean }) {
  const s = v.snmp
  const radio = v.enlaces.radio
  const redundante = v.enlaces.fibra.up && radio.up
  const div = <span className="h-5 w-px shrink-0 bg-fio-forte" />
  return (
    <div className="flex min-h-[52px] flex-wrap items-center gap-x-6 gap-y-2 rounded-[10px] border border-fio bg-painel px-7 py-2.5 text-[13px] text-tinta">
      <span>Host: {v.host}</span>
      {div}
      <span className="flex items-center gap-2">
        {radio.up
          ? <><CellSignalFull size={15} weight="fill" className="text-led" />Rádio {radio.sinal ?? '—'} dBm</>
          : <><CellSignalX size={15} weight="fill" className="text-desastre" />Rádio sem sinal</>}
      </span>
      {interno && s.cpu != null && <>{div}<span className="flex items-center gap-2"><Cpu size={15} weight="fill" className="text-led" />CPU {s.cpu}%</span></>}
      {interno && s.uptime != null && <>{div}<span>No ar há {duracao(s.uptime)}</span></>}
      {interno && s.routeros && <>{div}<span className="text-tinta-2">{s.modelo} · RouterOS {s.routeros}</span></>}
      <span className="ml-auto" title={redundante ? 'Com redundância: fibra e rádio no ar' : 'Sem redundância'}>
        {redundante ? <LinkSimple size={18} className="text-tinta-3" /> : <LinkBreak size={18} className="text-desastre" />}
      </span>
    </div>
  )
}

function CardAlertas({ alertas, baixar }: { alertas: Alerta[] | null; baixar: (nome: string, linhas: string[]) => void }) {
  const lista = alertas?.slice(0, 5) ?? []
  const destaque = lista.find(a => a.ativo && CRITICO.includes(a.severidade)) ?? lista.find(a => a.ativo)
  const criticos = alertas?.filter(a => CRITICO.includes(a.severidade)).length ?? 0
  return (
    <Card className="h-full" titulo="Alertas" acao={
      <Chip onClick={() => alertas && baixar('sennaguard-alertas.csv', ['evento;severidade;problema;inicio;fim',
        ...alertas.map(a => `${a.id};${a.severidade};${a.nome};${dataHora(a.inicio)};${a.fim ? dataHora(a.fim) : 'ativo'}`)])}>
        <DownloadSimple />Baixar
      </Chip>}>
      <ul className="flex flex-col gap-2">
        {lista.map(a => {
          const c = CRITICO.includes(a.severidade) ? 'var(--color-desastre)' : 'var(--color-media)'
          return (
            <li key={a.id}>
              <Link to={`/alertas?id=${a.id}`} title={a.nome}
                className={`flex h-[30px] items-center gap-2.5 rounded-full px-3 text-[12px] transition-colors hover:bg-pilula-hover ${a === destaque ? 'bg-destaque ring-1 ring-inset' : 'bg-painel-alto'}`}
                style={{ '--tw-ring-color': c } as React.CSSProperties}>
                <span className="size-1.5 shrink-0 rounded-full" style={{ background: c }} />
                <b className="shrink-0 font-semibold text-tinta">{curto(a.nome)}</b>
                <span className="num truncate text-tinta-2">às {dataHora(a.inicio).replace(',', '')} {a.ativo ? '(ativo)' : `(${duracao((a.fim ?? 0) - a.inicio)})`}</span>
              </Link>
            </li>
          )
        })}
      </ul>
      {alertas && (
        <div className="num mt-4 flex items-center gap-4 border-t border-fio pt-3 text-[11.5px] text-tinta-2">
          <span className="flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-desastre" />Crítico <b className="font-semibold text-tinta">{criticos}</b></span>
          <span className="flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-media" />Aviso <b className="font-semibold text-tinta">{alertas.length - criticos}</b></span>
          <span className="ml-auto">Total <b className="font-semibold text-tinta">{alertas.length}</b></span>
        </div>
      )}
    </Card>
  )
}

function CardChamados({ ch }: { ch: ListaChamados | null }) {
  return (
    <Card className="h-full" titulo="Seus chamados" acao={<Link to="/chamados?sg=novo"><Chip><Plus />Abrir</Chip></Link>}>
      <ul className="flex flex-col gap-2">
        {ch?.manuais.slice(0, 5).map(c => (
          <li key={c.id}>
            <Link to={`/chamados?sg=${c.id}`} title={c.titulo}
              className="flex h-[30px] items-center gap-2.5 rounded-full bg-painel-alto px-3 text-[12px] transition-colors hover:bg-pilula-hover">
              <b className="shrink-0 font-mono text-[11px] font-medium text-tinta-2">{c.numero}</b>
              <span className="min-w-0 flex-1 truncate text-tinta">{c.titulo}</span>
              <StatusChamado status={c.status} />
            </Link>
          </li>
        ))}
        {ch && !ch.manuais.length && <li className="py-8 text-center text-tinta-3">Nenhum chamado aberto.</li>}
      </ul>
      {ch && (
        <div className="num mt-4 flex items-center gap-4 border-t border-fio pt-3 text-[11.5px] text-tinta-2">
          <span>Em andamento <b className="font-semibold text-tinta">{ch.manuais.filter(c => c.status !== 'resolvido').length}</b></span>
          <span className="ml-auto">Total <b className="font-semibold text-tinta">{ch.manuais.length}</b></span>
        </div>
      )}
    </Card>
  )
}

/** Links de internet do R-MATRIZ: VIVO (principal) e TIN (backup); o ativo segue a regra do roteador. */
function CardInternet({ i }: { i: TVisao['internet'] }) {
  const pilula = i == null ? null : i.ativo == null
    ? <span className="inline-flex items-center gap-1.5 rounded-full bg-desastre/15 px-2 py-0.5 text-[11px] font-semibold text-desastre"><span className="size-1.5 rounded-full bg-current" />Sem internet</span>
    : <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold ${i.ativo === 'vivo' ? 'bg-led/15 text-led' : 'bg-radio/15 text-radio'}`}>
      <span className="size-1.5 rounded-full bg-current" />{i.ativo === 'vivo' ? 'Pela VIVO' : 'Pelo TIN (backup)'}</span>
  const linha = (nome: string, papel: string, l: LinkWan, ativo: boolean) => (
    <li className="grid grid-cols-[10px_minmax(0,1fr)_auto] items-center gap-3 border-t border-fio py-2.5 text-[12px]">
      <span className={`size-2 rounded-full ${l.up ? 'bg-led' : 'bg-desastre'}`} />
      <span className="min-w-0 truncate"><b className={`font-semibold ${ativo ? 'text-tinta' : 'text-tinta-2'}`}>{nome}</b> <span className="text-tinta-3">· {papel}{l.ip ? ` · ${l.ip}` : ''}</span></span>
      <span className="num text-tinta-2">{l.up ? `${l.latencia?.toLocaleString('pt-BR') ?? '—'} ms` : 'fora'}</span>
    </li>
  )
  return (
    <Card className="h-full" titulo="Internet">
      {i == null ? <p className="py-6 text-center text-tinta-3">Sem dados do R-MATRIZ.</p> : <>
        <div className="text-[11px] text-tinta-2">Saída da rede<div className="mt-1.5">{pilula}</div></div>
        <ul className="mt-4">
          {linha('VIVO', 'principal', i.vivo, i.ativo === 'vivo')}
          {linha('TIN', 'backup', i.tin, i.ativo === 'tin')}
        </ul>
      </>}
    </Card>
  )
}

/** Equivalente ao "Door Activity": situação do caminho, trocas e uma régua com quedas (blocos) e alertas (riscos). */
function CardCaminho({ pontos, v, alertas }: { pontos: Ponto[]; v: TVisao; alertas: Alerta[] }) {
  const t0 = pontos[0]?.t ?? 0, t1 = pontos[pontos.length - 1]?.t ?? 1
  const x = (t: number) => `${Math.min(100, Math.max(0, ((t - t0) / (t1 - t0)) * 100))}%`
  const quedas = faixasSemResposta(pontos, 'fibra', '')
  const noRadio = quedas.reduce((s, f) => s + (f.fim - f.ini), 0)
  const naFibra = v.caminho === 'fibra'
  const riscos = alertas.filter(a => a.inicio >= t0 && a.inicio <= t1)
  return (
    <Card className="h-full" titulo="Caminho ativo" acao={<Link to="/equipamentos"><Chip><ArrowsOut />Detalhes</Chip></Link>}>
      <div className="grid grid-cols-3 divide-x divide-fio-forte text-[11px] text-tinta-2">
        <div className="pr-3">
          Situação
          <div className="mt-1.5">
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold ${naFibra ? 'bg-led/15 text-led' : 'bg-desastre/15 text-desastre'}`}>
              <span className="size-1.5 rounded-full bg-current" />{naFibra ? 'Na fibra' : 'No rádio'}
            </span>
          </div>
        </div>
        <div className="px-3">Trocas<div className="num mt-1 text-[16px] font-semibold text-tinta">{quedas.length}</div></div>
        <div className="pl-3">No rádio<div className="num mt-1 text-[16px] font-semibold text-tinta">{noRadio ? duracao(noRadio) : '0 min'}</div></div>
      </div>
      <div className="relative mt-5 h-[34px]" role="img" aria-label="Quedas da fibra (blocos) e alertas (riscos) no período">
        {riscos.map(a => <span key={a.id} title={`${hora(a.inicio)} · ${a.nome}`} className="absolute inset-y-0 w-[2px] rounded-[1px] bg-risco" style={{ left: x(a.inicio) }} />)}
        {quedas.map(f => <span key={f.ini} title={`Fibra fora: ${hora(f.ini)} às ${hora(f.fim)}`} className="absolute inset-y-0 min-w-[10px] rounded-[2px] bg-queda" style={{ left: x(f.ini), width: `calc(${x(f.fim)} - ${x(f.ini)})` }} />)}
      </div>
      <div className="num mt-2 flex justify-between border-t border-fio pt-1.5 text-[10.5px] text-tinta-3">
        {[t0, (t0 + t1) / 2, t1].map(t => <span key={t}>{t1 - t0 > 36 * 3600 ? dataHora(t) : hora(t)}</span>)}
      </div>
    </Card>
  )
}

