import { useEffect, useRef, useState, type ClipboardEvent, type FormEvent } from 'react'
import { Checks, Check, Clock, FilePdf, LockSimple, Lightbulb, Paperclip, X } from '@phosphor-icons/react'
import { CheckCircle2, Loader2, Send, Wrench } from 'lucide-react'
import { api, enviarArquivo, urlAnexo, type Anexo, type ChamadoManual, type ContextoEnlace, type Registro } from '../lib/api'
import { dataHora, desde, duracao } from '../lib/fmt'
import { useSessao } from '../lib/sessao'
import { Botao, Led } from './ui'

export const CATEGORIAS: Record<string, string> = {
  sem_acesso: 'Sem acesso à rede', lentidao: 'Lentidão', instavel: 'Quedas intermitentes', outro: 'Outro problema',
}
export const IMPACTOS: Record<string, string> = { um_pc: 'Um computador', setor: 'Um setor', filial: 'A Filial inteira' }
const STATUS: Record<string, { rotulo: string; cor: string }> = {
  aberto: { rotulo: 'Aberto', cor: 'var(--color-media)' },
  em_atendimento: { rotulo: 'Em atendimento', cor: 'var(--color-fibra)' },
  resolvido: { rotulo: 'Resolvido', cor: 'var(--color-led)' },
}
const ACOES: Record<string, string> = {
  abertura: 'abriu o chamado', comentario: 'comentou', nota: 'escreveu uma nota interna', em_atendimento: 'assumiu o atendimento',
  resolvido: 'marcou como resolvido', aberto: 'voltou para aberto', reaberto: 'reabriu ao responder',
}

/** Situação do SLA (24x7): o prazo que está correndo agora, ou como terminou. */
export function estadoSla(c: ChamadoManual) {
  const agora = Date.now() / 1000
  const { resposta, solucao } = c.sla
  if (c.status === 'resolvido' && solucao.em)
    return solucao.em <= solucao.prazo && (resposta.em ?? solucao.em) <= resposta.prazo
      ? { texto: 'Resolvido no prazo', cor: 'var(--color-led)' } : { texto: 'Resolvido fora do prazo', cor: 'var(--color-desastre)' }
  const etapa = resposta.em ? { nome: 'Resolver', ...solucao } : { nome: 'Responder', ...resposta }
  const falta = etapa.prazo - agora
  if (falta < 0) return { texto: `${etapa.nome === 'Responder' ? 'Resposta' : 'Solução'} atrasada ${duracao(-falta)}`, cor: 'var(--color-desastre)' }
  const total = etapa.prazo - c.criado_em
  return { texto: `${etapa.nome} em ${duracao(falta)}`, cor: falta < total * 0.25 ? 'var(--color-alta)' : 'var(--color-tinta-2)' }
}

export function SlaChip({ c }: { c: ChamadoManual }) {
  const e = estadoSla(c)
  return <span className="num inline-flex items-center gap-1.5 text-[12px] font-medium" style={{ color: e.cor }}><Clock size={13} weight="bold" />{e.texto}</span>
}

function BarraSla({ rotulo, inicio, prazo, em }: { rotulo: string; inicio: number; prazo: number; em: number | null }) {
  const fim = em ?? Date.now() / 1000
  const frac = Math.min(1, (fim - inicio) / (prazo - inicio))
  const estourou = fim > prazo
  const cor = estourou ? 'var(--color-desastre)' : em ? 'var(--color-led)' : frac > 0.75 ? 'var(--color-alta)' : 'var(--color-fibra)'
  return (
    <div>
      <div className="flex justify-between text-[11px]">
        <span className="text-tinta-3">{rotulo} · prazo {duracao(prazo - inicio)}</span>
        <span className="num font-medium" style={{ color: cor }}>
          {em ? `${estourou ? 'atrasou' : 'cumprido em'} ${duracao(em - inicio)}` : estourou ? `atrasado ${duracao(fim - prazo)}` : `faltam ${duracao(prazo - fim)}`}
        </span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-painel-alto">
        <div className="h-full rounded-full" style={{ width: `${Math.max(3, frac * 100)}%`, background: cor }} />
      </div>
    </div>
  )
}

export function StatusChamado({ status }: { status: string }) {
  const s = STATUS[status]
  return <span className="inline-flex items-center gap-1.5 text-[12px] font-medium" style={{ color: s.cor }}><Led cor={s.cor} pulsa={status === 'aberto'} />{s.rotulo}</span>
}

const campo = 'w-full rounded-lg border border-fio bg-fenda px-3 text-tinta placeholder:text-tinta-4 focus:border-fibra/60 focus:outline-none'

function Opcoes({ legenda, opcoes, valor, onChange, colunas }: { legenda: string; opcoes: Record<string, string>; valor: string; onChange: (v: string) => void; colunas: string }) {
  return (
    <fieldset>
      <legend className="mb-1.5 text-[12px] font-medium text-tinta-2">{legenda}</legend>
      <div className={`grid gap-2 ${colunas}`}>
        {Object.entries(opcoes).map(([v, r]) => (
          <label key={v} className={`flex h-9 cursor-pointer items-center justify-center rounded-lg border px-2 text-center text-[12px] font-medium transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-fibra ${valor === v ? 'border-fibra/60 bg-fibra/10 text-tinta' : 'border-fio text-tinta-3 hover:border-fio-forte hover:text-tinta-2'}`}>
            <input type="radio" className="sr-only" checked={valor === v} onChange={() => onChange(v)} />{r}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

const TIPOS = ['image/png', 'image/jpeg', 'image/webp', 'application/pdf']
const LIMITE = 5 * 1024 * 1024
const tamanho = (b: number) => b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} MB`

/** Anexos de uma mensagem que ainda vai ser enviada: cada arquivo sobe na hora em que é escolhido (ou colado). */
function useAnexos() {
  const [lista, setLista] = useState<Anexo[]>([])
  const [subindo, setSubindo] = useState(0)
  const [erro, setErro] = useState('')
  const adicionar = async (arquivos: File[]) => {
    setErro('')
    for (const f of arquivos) {
      if (!TIPOS.includes(f.type)) { setErro(`"${f.name}": envie imagem (PNG, JPG, WEBP) ou PDF.`); continue }
      if (f.size > LIMITE) { setErro(`"${f.name}" passa de 5 MB.`); continue }
      if (lista.length + subindo >= 5) { setErro('No máximo 5 anexos por mensagem.'); break }
      setSubindo(n => n + 1)
      try {
        const a = await enviarArquivo<Anexo>(`/api/anexos?nome=${encodeURIComponent(f.name || 'print.png')}`, f)
        setLista(l => [...l, a])
      } catch (e) { setErro((e as Error).message) } finally { setSubindo(n => n - 1) }
    }
  }
  const colar = (e: ClipboardEvent) => {
    const imgs = [...e.clipboardData.files].filter(f => f.type.startsWith('image/'))
    if (imgs.length) { e.preventDefault(); adicionar(imgs) }
  }
  return { lista, subindo, erro, adicionar, colar, remover: (id: number) => setLista(l => l.filter(a => a.id !== id)), limpar: () => setLista([]) }
}

function EscolherAnexos({ an }: { an: ReturnType<typeof useAnexos> }) {
  const entrada = useRef<HTMLInputElement>(null)
  return (
    <div className="flex flex-col gap-2">
      {(an.lista.length > 0 || an.subindo > 0) && (
        <ul className="flex flex-wrap gap-2">
          {an.lista.map(a => (
            <li key={a.id} className="flex h-8 max-w-[220px] items-center gap-1.5 rounded-lg border border-fio bg-painel-alto pl-2.5 pr-1 text-[12px]">
              {a.tipo === 'application/pdf' ? <FilePdf size={14} weight="fill" className="shrink-0 text-desastre" /> : <Paperclip size={14} className="shrink-0 text-tinta-3" />}
              <span className="truncate">{a.nome}</span>
              <button type="button" onClick={() => an.remover(a.id)} aria-label={`Tirar ${a.nome}`} className="grid size-6 shrink-0 place-items-center rounded text-tinta-3 hover:text-tinta"><X size={12} weight="bold" /></button>
            </li>
          ))}
          {an.subindo > 0 && <li className="flex h-8 items-center gap-1.5 px-2 text-[12px] text-tinta-3"><Loader2 className="size-3.5 animate-spin" />enviando…</li>}
        </ul>
      )}
      {an.erro && <p className="text-[12px] text-desastre">{an.erro}</p>}
      <input ref={entrada} type="file" multiple accept={TIPOS.join(',')} className="sr-only" tabIndex={-1}
        onChange={e => { an.adicionar([...(e.target.files ?? [])]); e.target.value = '' }} />
      <button type="button" onClick={() => entrada.current?.click()} className="flex items-center gap-1.5 self-start text-[12px] font-medium text-tinta-2 hover:text-tinta">
        <Paperclip size={15} />Anexar print, foto ou PDF <span className="font-normal text-tinta-4">· até 5 MB · Ctrl+V cola um print</span>
      </button>
    </div>
  )
}

/** Anexos de uma mensagem já enviada: imagens em miniatura (abrem em outra aba), PDF como etiqueta para baixar. */
function Anexos({ lista }: { lista: Anexo[] }) {
  if (!lista.length) return null
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {lista.map(a => a.tipo.startsWith('image/')
        ? <a key={a.id} href={urlAnexo(a.id)} target="_blank" rel="noreferrer" title={a.nome} className="block overflow-hidden rounded-lg ring-1 ring-fio-forte transition-opacity hover:opacity-85">
            <img src={urlAnexo(a.id)} alt={a.nome} loading="lazy" className="h-20 w-28 object-cover" />
          </a>
        : <a key={a.id} href={urlAnexo(a.id)} className="flex h-9 max-w-[240px] items-center gap-2 rounded-lg border border-fio bg-painel-alto px-3 text-[12px] hover:border-fio-forte">
            <FilePdf size={16} weight="fill" className="shrink-0 text-desastre" /><span className="truncate">{a.nome}</span><span className="shrink-0 text-tinta-4">{tamanho(a.tamanho)}</span>
          </a>)}
    </div>
  )
}

/** Formulário de abertura: o estado do enlace é anexado pelo servidor, o cliente só descreve o problema. */
export function NovoChamado({ onCriado, onCancelar }: { onCriado: (c: ChamadoManual) => void; onCancelar: () => void }) {
  const [f, setF] = useState({ titulo: '', descricao: '', categoria: 'sem_acesso', impacto: 'um_pc' })
  const [erro, setErro] = useState('')
  // Sugestões da base de conhecimento enquanto a pessoa descreve o problema (espera 500 ms de pausa na digitação)
  const [sugestoes, setSugestoes] = useState<{ id: number; titulo: string; solucao: string }[]>([])
  const [vendo, setVendo] = useState<number | null>(null)
  useEffect(() => {
    const q = `${f.titulo} ${f.descricao}`.trim()
    if (q.length < 8) { setSugestoes([]); return }
    const t = setTimeout(() => api<typeof sugestoes>(`/api/conhecimento/sugestoes?q=${encodeURIComponent(q)}`).then(setSugestoes).catch(() => {}), 500)
    return () => clearTimeout(t)
  }, [f.titulo, f.descricao])
  const [enviando, setEnviando] = useState(false)
  const an = useAnexos()
  const enviar = async (e: FormEvent) => {
    e.preventDefault(); setErro(''); setEnviando(true)
    try { onCriado(await api<ChamadoManual>('/api/chamados', { method: 'POST', body: JSON.stringify({ ...f, anexos: an.lista.map(a => a.id) }) })) }
    catch (x) { setErro((x as Error).message) } finally { setEnviando(false) }
  }
  return (
    <form onSubmit={enviar} className="flex flex-col gap-4">
      <Opcoes legenda="O que está acontecendo?" opcoes={CATEGORIAS} valor={f.categoria} onChange={categoria => setF({ ...f, categoria })} colunas="grid-cols-2" />
      <Opcoes legenda="Quem é afetado?" opcoes={IMPACTOS} valor={f.impacto} onChange={impacto => setF({ ...f, impacto })} colunas="grid-cols-3" />
      <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">Título
        <input required minLength={4} maxLength={120} value={f.titulo} onChange={e => setF({ ...f, titulo: e.target.value })}
          placeholder="Ex.: Sem internet no setor financeiro" className={`${campo} h-9`} />
      </label>
      <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">Descrição
        <textarea required minLength={10} maxLength={4000} rows={4} value={f.descricao} onChange={e => setF({ ...f, descricao: e.target.value })} onPaste={an.colar}
          placeholder="Desde quando, quais computadores, o que aparece na tela…" className={`${campo} resize-none py-2`} />
      </label>
      <EscolherAnexos an={an} />
      {sugestoes.length > 0 && (
        <div className="rounded-xl border border-fibra/30 bg-fibra/[0.07] px-4 py-3">
          <div className="mb-1.5 flex items-center gap-1.5 text-[12px] font-semibold text-tinta"><Lightbulb size={15} weight="fill" className="text-fibra" />Isso pode resolver antes de abrir o chamado</div>
          <ul className="flex flex-col gap-1">
            {sugestoes.map(s => (
              <li key={s.id}>
                <button type="button" onClick={() => setVendo(vendo === s.id ? null : s.id)} className="text-left text-[12.5px] font-medium text-fibra hover:underline">{s.titulo}</button>
                {vendo === s.id && <p className="mt-1 whitespace-pre-wrap text-[12px] leading-relaxed text-tinta-2">{s.solucao}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-[11px] leading-snug text-tinta-3">O estado da fibra e do rádio neste momento é anexado ao chamado automaticamente.</p>
      {erro && <p className="text-[12px] text-desastre">{erro}</p>}
      <div className="flex justify-end gap-2 border-t border-fio pt-4">
        <Botao type="button" onClick={onCancelar}>Cancelar</Botao>
        <Botao type="submit" variante="primario" disabled={enviando || an.subindo > 0}><Send />{enviando ? 'Abrindo…' : 'Abrir chamado'}</Botao>
      </div>
    </form>
  )
}

/** O enlace no instante da abertura, no mesmo desenho do trilho. */
function Foto({ c }: { c: ContextoEnlace }) {
  const linha = (nome: string, up: boolean, ativo: boolean, ms: string, cor: string) => (
    <div className="flex items-center gap-3 text-[12px]">
      <span className="w-12 font-semibold tracking-[0.06em] text-tinta-3">{nome}</span>
      <span className="h-[2px] flex-1 rounded" style={{ background: up ? cor : 'var(--color-desastre)', opacity: up ? (ativo ? 1 : 0.4) : 0.8 }} />
      <span className="num w-28 text-right font-mono" style={{ color: up ? 'var(--color-tinta-2)' : 'var(--color-desastre)' }}>{up ? (ativo ? `ativo · ${ms}` : 'em espera') : 'fora'}</span>
    </div>
  )
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-fio bg-fenda px-4 py-3">
      <div className="text-[11px] font-medium text-tinta-3">Enlace no momento da abertura</div>
      {linha('FIBRA', c.fibra_up, c.caminho === 'fibra', c.fibra_ms, 'var(--color-fibra)')}
      {linha('RÁDIO', c.radio_up, c.caminho === 'radio', c.radio_ms, 'var(--color-radio)')}
    </div>
  )
}

/** Linha de um evento (assumiu, resolveu, reabriu): pequena e centralizada, para não competir com a conversa. */
function Evento({ r }: { r: Registro }) {
  return (
    <li className="flex items-center gap-3 text-[11.5px] text-tinta-3">
      <span className="h-px flex-1 bg-fio" />
      <span><b className="font-medium text-tinta-2">{r.autor_nome}</b> {ACOES[r.acao] ?? r.acao} · {dataHora(r.em)}</span>
      <span className="h-px flex-1 bg-fio" />
    </li>
  )
}

/** Mensagem da conversa. As minhas ficam à direita; nota interna em âmbar, só para a equipe. */
function Mensagem({ r, minha, descricao }: { r: Registro; minha: boolean; descricao: string }) {
  const nota = r.acao === 'nota'
  const daEquipe = r.autor_papel !== 'Cliente'
  const texto = r.acao === 'abertura' ? descricao : r.texto // a abertura guarda título + descrição; o título já está no topo
  return (
    <li className={`flex flex-col ${minha ? 'items-end' : 'items-start'}`}>
      <div className="mb-1 flex items-center gap-1.5 text-[11.5px] text-tinta-3">
        {nota && <LockSimple size={12} weight="fill" className="text-media" />}
        <b className="font-semibold text-tinta-2">{r.autor_nome}</b>
        <span>{nota ? 'nota interna' : r.acao === 'abertura' ? 'abriu o chamado' : daEquipe ? 'NOC' : 'Filial'} · {dataHora(r.em)}</span>
      </div>
      <div className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 leading-relaxed ${nota ? 'border border-dashed border-media/50 bg-media/10'
        : minha ? 'rounded-tr-md bg-fibra/15' : 'rounded-tl-md bg-painel-alto'}`}>
        {texto && <p className="whitespace-pre-wrap text-tinta">{texto}</p>}
        <Anexos lista={r.anexos} />
      </div>
      {minha && !nota && (
        <div className="mt-1 flex items-center gap-1 text-[10.5px] text-tinta-4" title={r.visto ? `Visto por ${r.visto.por}` : undefined}>
          {r.visto ? <><Checks size={13} weight="bold" className="text-fibra" />Visto {daEquipe ? 'pelo cliente' : 'pelo NOC'} às {dataHora(r.visto.em).split(' ')[1]}</> : <><Check size={13} weight="bold" />Enviado</>}
        </div>
      )}
    </li>
  )
}

export function DetalheChamado({ id, onMudou }: { id: number; onMudou: () => void }) {
  const { pode, eu } = useSessao()
  const [c, setC] = useState<ChamadoManual | null>(null)
  const [texto, setTexto] = useState('')
  const [interno, setInterno] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [erro, setErro] = useState('')
  const an = useAnexos()
  const fim = useRef<HTMLDivElement>(null)
  // Recarrega quando o outro lado responde ou lê (tempo real pelo canal "chamados")
  useEffect(() => {
    const carregar = () => api<ChamadoManual>(`/api/chamados/manuais/${id}`).then(setC).catch(() => {})
    carregar()
    window.addEventListener('sg:chamados', carregar)
    return () => window.removeEventListener('sg:chamados', carregar)
  }, [id])
  const mensagens = c?.registros?.filter(r => ['abertura', 'comentario', 'nota'].includes(r.acao)).length ?? 0
  useEffect(() => { fim.current?.scrollIntoView({ block: 'nearest' }) }, [mensagens])

  const agir = async (url: string, corpo: object) => {
    setOcupado(true); setErro('')
    try { setC(await api<ChamadoManual>(url, { method: 'POST', body: JSON.stringify(corpo) })); onMudou(); return true }
    catch (e) { setErro((e as Error).message); return false } finally { setOcupado(false) }
  }
  const responder = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado || an.subindo > 0 || (!texto.trim() && !an.lista.length)) return // mesma trava do botão Enviar
    if (await agir(`/api/chamados/manuais/${id}/comentario`, { texto, interno, anexos: an.lista.map(a => a.id) })) { setTexto(''); an.limpar() }
  }
  if (!c) return <div className="grid h-40 place-items-center text-tinta-3"><Loader2 className="size-5 animate-spin" /></div>
  const cliente = eu?.papel === 'Cliente'

  return (
    <div className="flex flex-col gap-6">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
        <div><dt className="text-[11px] text-tinta-3">Situação</dt><dd className="mt-1"><StatusChamado status={c.status} /></dd></div>
        <div><dt className="text-[11px] text-tinta-3">Responsável</dt><dd className="mt-1 font-medium">{c.responsavel_nome ?? <span className="text-tinta-3">Ninguém ainda</span>}</dd></div>
        <div><dt className="text-[11px] text-tinta-3">Problema</dt><dd className="mt-1 font-medium">{CATEGORIAS[c.categoria]}</dd></div>
        <div><dt className="text-[11px] text-tinta-3">Afeta</dt><dd className="mt-1 font-medium">{IMPACTOS[c.impacto]}</dd></div>
      </dl>

      <div className="flex flex-col gap-3 rounded-xl border border-fio px-4 py-3">
        <BarraSla rotulo="Primeira resposta" inicio={c.criado_em} prazo={c.sla.resposta.prazo} em={c.sla.resposta.em} />
        <BarraSla rotulo="Solução" inicio={c.criado_em} prazo={c.sla.solucao.prazo} em={c.sla.solucao.em} />
      </div>

      {c.contexto && <Foto c={c.contexto} />}

      {pode('atender_chamado') && c.status !== 'resolvido' && (
        <div className="flex flex-wrap gap-2">
          {c.status === 'aberto' && <Botao variante="primario" disabled={ocupado} onClick={() => agir(`/api/chamados/manuais/${c.id}/status`, { status: 'em_atendimento' })}><Wrench />Assumir atendimento</Botao>}
          <Botao disabled={ocupado} onClick={() => agir(`/api/chamados/manuais/${c.id}/status`, { status: 'resolvido' })}><CheckCircle2 />Marcar como resolvido</Botao>
        </div>
      )}

      <section>
        <h3 className="mb-3 text-[13px] font-semibold">Conversa</h3>
        <ol className="flex flex-col gap-4">
          {c.registros?.map(r => ['abertura', 'comentario', 'nota'].includes(r.acao)
            ? <Mensagem key={r.seq} r={r} descricao={c.descricao} minha={r.autor_nome === eu?.nome && (r.autor_papel === 'Cliente') === cliente} />
            : <Evento key={r.seq} r={r} />)}
        </ol>
        <div ref={fim} />
      </section>

      <form onSubmit={responder} className={`flex flex-col gap-2.5 rounded-xl border p-3 ${interno ? 'border-dashed border-media/50 bg-media/[0.06]' : 'border-fio'}`}>
        {!cliente && (
          <div className="flex gap-1 text-[12px]">
            {[{ v: false, r: 'Responder ao cliente' }, { v: true, r: 'Nota interna' }].map(o => (
              <button key={o.r} type="button" aria-pressed={interno === o.v} onClick={() => setInterno(o.v)}
                className={`flex h-7 items-center gap-1.5 rounded-md px-2.5 font-medium transition-colors ${interno === o.v ? (o.v ? 'bg-media/20 text-tinta' : 'bg-painel-alto text-tinta') : 'text-tinta-3 hover:text-tinta-2'}`}>
                {o.v && <LockSimple size={12} weight="fill" />}{o.r}
              </button>
            ))}
          </div>
        )}
        <label htmlFor="resp" className="sr-only">{cliente ? 'Responder ao NOC' : interno ? 'Nota interna' : 'Responder ao cliente'}</label>
        <textarea id="resp" rows={3} value={texto} onChange={e => setTexto(e.target.value)} onPaste={an.colar} maxLength={4000}
          // Enter envia, Shift+Enter pula linha (isComposing: não envia no meio de um acento sendo digitado)
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); responder(e) } }}
          placeholder={interno ? 'Só a equipe vê. O cliente não é avisado.' : c.status === 'resolvido' && cliente ? 'Se o problema voltou, conte aqui: o chamado é reaberto.' : 'Escreva uma mensagem…'}
          className={`${campo} resize-none py-2`} />
        <EscolherAnexos an={an} />
        {erro && <p className="text-[12px] text-desastre">{erro}</p>}
        <div className="flex items-center justify-between gap-2">
          <span className="hidden text-[11px] text-tinta-4 sm:inline">Enter envia · Shift+Enter pula linha</span>
          <Botao type="submit" variante="primario" className="ml-auto" disabled={ocupado || an.subindo > 0 || (!texto.trim() && !an.lista.length)}>
            {interno ? <LockSimple weight="fill" /> : <Send />}{interno ? 'Salvar nota' : 'Enviar'}
          </Botao>
        </div>
      </form>

      <details className="text-[11px] text-tinta-4">
        <summary className="cursor-pointer select-none text-center">Registro encadeado (SHA-256) · {c.registros?.length} entradas</summary>
        <ol className="mt-2 flex flex-col gap-1 font-mono text-[10px]">
          {c.registros?.map(r => <li key={r.seq} className="truncate" title={r.hash}>#{r.seq} {r.acao} · {r.hash.slice(0, 32)}…</li>)}
        </ol>
      </details>
      <p className="text-center text-[11px] text-tinta-4">Aberto por {c.aberto_por_nome} há {desde(c.criado_em)}</p>
    </div>
  )
}
