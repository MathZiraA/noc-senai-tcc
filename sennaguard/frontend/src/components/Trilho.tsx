import type { Enlace, Visao } from '../lib/api'
import { desde, hora, ms } from '../lib/fmt'
import { Led } from './ui'

type Estado = 'ativo' | 'espera' | 'fora'
const corEnlace = { fibra: 'var(--color-fibra)', radio: 'var(--color-radio)' }

function estado(nome: 'fibra' | 'radio', e: Enlace, caminho: string): Estado {
  if (!e.up) return 'fora'
  return caminho === nome ? 'ativo' : 'espera'
}

/** Uma linha do trilho: o enlace como um cabo entre os dois nós. */
function Linha({ nome, e, est }: { nome: 'fibra' | 'radio'; e: Enlace; est: Estado }) {
  const cor = est === 'fora' ? 'var(--color-desastre)' : corEnlace[nome]
  return (
    <div className="relative">
      <div className="mb-1.5 flex items-baseline justify-between text-[11px]">
        <span className="font-semibold tracking-[0.08em]" style={{ color: est === 'fora' ? cor : 'var(--color-tinta-2)' }}>
          {nome === 'fibra' ? 'FIBRA' : 'RÁDIO'}
          <span className="ml-2 font-mono font-normal tracking-normal text-tinta-4">{e.porta} · custo {e.custo}</span>
        </span>
        <span className="num font-mono text-tinta-2">{est === 'fora' ? `${e.perda ?? 100}% perda` : ms(e.latencia)}</span>
      </div>
      <svg className="block h-3 w-full overflow-visible" aria-hidden>
        {est === 'ativo' && <>
          <line x1="0" y1="6" x2="100%" y2="6" stroke={cor} strokeOpacity=".25" strokeWidth="6" strokeLinecap="round" />
          <line x1="0" y1="6" x2="100%" y2="6" stroke={cor} strokeWidth="2" strokeDasharray="8 4" className="trilho-ativo" />
        </>}
        {est === 'espera' && <line x1="0" y1="6" x2="100%" y2="6" stroke={cor} strokeOpacity=".45" strokeWidth="2" />}
        {est === 'fora' && <>
          <line x1="0" y1="6" x2="44%" y2="6" stroke={cor} strokeOpacity=".7" strokeWidth="2" strokeDasharray="3 4" />
          <line x1="56%" y1="6" x2="100%" y2="6" stroke={cor} strokeOpacity=".7" strokeWidth="2" strokeDasharray="3 4" />
        </>}
      </svg>
      <div className="absolute left-1/2 top-[22px] -translate-x-1/2 -translate-y-1/2">
        <span className="inline-flex items-center gap-1.5 rounded-full border bg-painel px-2.5 py-0.5 text-[11px] font-semibold"
          style={{ color: est === 'espera' ? 'var(--color-tinta-3)' : cor, borderColor: `color-mix(in srgb, ${est === 'espera' ? 'var(--color-tinta-4)' : cor} 40%, transparent)` }}>
          {est === 'ativo' && <><Led cor={cor} pulsa />levando o tráfego</>}
          {est === 'espera' && 'em espera'}
          {est === 'fora' && <>fora{e.desde ? ` há ${desde(e.desde)}` : ''}</>}
        </span>
      </div>
    </div>
  )
}

function No({ nome, ip, lan, lado, onNo }: { nome: string; ip: string; lan: string; lado: 'esq' | 'dir'; onNo?: (nome: string) => void }) {
  const Tag = onNo ? 'button' : 'div'
  return (
    <Tag onClick={onNo ? () => onNo(nome) : undefined} title={onNo ? `Ver interfaces e recursos de ${nome}` : undefined}
      className={`w-[132px] shrink-0 rounded-xl border border-fio-forte bg-painel-alto px-3.5 py-3 text-left transition-colors ${lado === 'dir' ? 'text-right' : ''} ${onNo ? 'cursor-pointer hover:border-fibra/60 hover:bg-pilula-hover' : ''}`}>
      <div className="text-[11px] font-medium text-tinta-3">{lado === 'esq' ? 'Matriz' : 'Filial'}</div>
      <div className="mt-0.5 font-semibold">{nome}</div>
      <div className="mt-2 font-mono text-[11px] leading-relaxed text-tinta-3">{ip}<br />{lan}</div>
    </Tag>
  )
}

/** Frase que resume o estado da redundância: é o que o operador lê primeiro. */
export function resumo(v: Visao) {
  const { fibra, radio } = v.enlaces
  if (!fibra.up && !radio.up) return { texto: 'Filial isolada: fibra e rádio fora.', cor: 'var(--color-desastre)' }
  if (!fibra.up) return { texto: 'Fibra fora. O rádio está segurando a Filial.', cor: 'var(--color-alta)' }
  if (!radio.up) return { texto: 'Tráfego pela fibra, mas sem backup: o rádio está fora.', cor: 'var(--color-media)' }
  return { texto: 'Tráfego pela fibra, rádio pronto para assumir.', cor: 'var(--color-led)' }
}

export default function Trilho({ v, onNo }: { v: Visao; onNo?: (nome: string) => void }) {
  const r = resumo(v)
  const f = v.ultimo_failover
  return (
    <section className="rounded-xl border border-fio bg-painel">
      <div className="flex flex-wrap items-end justify-between gap-6 px-6 pb-2 pt-5">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-medium text-tinta-3"><Led cor={r.cor} pulsa={r.cor !== 'var(--color-led)'} />Caminho ativo agora</div>
          <h1 className="mt-1.5 text-[22px] font-semibold leading-tight tracking-[-0.02em]">{r.texto}</h1>
        </div>
        {f && (
          <div className="flex items-end gap-6 text-right">
            <div>
              <div className="num text-[28px] font-semibold leading-none tracking-[-0.02em] text-fibra">{f.segundos.toLocaleString('pt-BR')}<span className="ml-0.5 text-[15px] text-tinta-3">s</span></div>
              <div className="mt-1.5 text-[11px] text-tinta-3">último failover · {hora(f.em)}</div>
            </div>
            {v.disponibilidade_24h && (
              <div>
                <div className="num text-[28px] font-semibold leading-none tracking-[-0.02em]">{v.disponibilidade_24h.filial.toLocaleString('pt-BR')}<span className="ml-0.5 text-[15px] text-tinta-3">%</span></div>
                <div className="mt-1.5 text-[11px] text-tinta-3">Filial no ar · 24 h</div>
              </div>
            )}
          </div>
        )}
      </div>
      <div className="flex items-center gap-4 px-6 pb-6 pt-4">
        <No nome="R-MATRIZ" ip="10.255.255.1" lan="192.168.10.0/24" lado="esq" onNo={onNo} />
        <div className="flex min-w-0 flex-1 flex-col gap-7 pb-3">
          <Linha nome="fibra" e={v.enlaces.fibra} est={estado('fibra', v.enlaces.fibra, v.caminho)} />
          <Linha nome="radio" e={v.enlaces.radio} est={estado('radio', v.enlaces.radio, v.caminho)} />
        </div>
        <No nome="R-FILIAL" ip="10.255.255.2" lan="192.168.20.0/24" lado="dir" onNo={onNo} />
      </div>
    </section>
  )
}

/** O trilho em miniatura, para listas de alertas e chamados: qual enlace o evento atinge. */
export function TrilhoMini({ nome }: { nome: string }) {
  // "Link FIBRA caiu: failover para RÁDIO ativo" atinge a fibra: o assunto vem antes dos dois-pontos.
  const n = nome.toUpperCase()
  const assunto = /FIBRA|RÁDIO|ISOLADA/.test(n.split(':')[0]) ? n.split(':')[0] : n
  const fibra = assunto.includes('FIBRA') || assunto.includes('ISOLADA')
  const radio = assunto.includes('RÁDIO') || assunto.includes('ISOLADA')
  const linha = (atingido: boolean, cor: string) => (
    <span className="block h-[2px] w-full rounded" style={{ background: atingido ? 'var(--color-desastre)' : cor, opacity: atingido ? 1 : 0.35 }} />
  )
  return (
    <span className="flex w-7 shrink-0 flex-col gap-[3px]" aria-hidden>
      {linha(fibra, 'var(--color-fibra)')}
      {linha(radio, 'var(--color-radio)')}
    </span>
  )
}
