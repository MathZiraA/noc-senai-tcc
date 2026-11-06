import { useState } from 'react'
import { Area, AreaChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { WarningCircle } from '@phosphor-icons/react'
import type { Ponto } from '../lib/api'
import { dataHora, hora } from '../lib/fmt'

/** `critico` = linha vermelha tracejada (a área acima dela fica rosa); `normal` = referência da bancada. */
export type Limite = { valor: number; rotulo: string; tipo: 'critico' | 'normal' }
export type Faixa = { ini: number; fim: number; rotulo: string }

const horaCurta = (t: number) => hora(t).replace(/^0/, '')
const fmt = (v: number) => v.toLocaleString('pt-BR', { maximumFractionDigits: v < 10 ? 1 : 0 })

/** `inverso`: valor menor é pior (sinal em dBm): escala com negativos e área rosa ABAIXO do limite crítico.
 *  `onZoom`: arrastar o mouse sobre o gráfico seleciona um trecho e devolve o intervalo (segundos Unix). */
export default function Grafico({ dados, serie, cor, unidade, limites = [], faixas = [], altura = 220, inverso = false, onZoom }: {
  dados: Ponto[]; serie: string; cor: string; unidade: string; limites?: Limite[]; faixas?: Faixa[]; altura?: number; inverso?: boolean
  onZoom?: (de: number, ate: number) => void
}) {
  const [sel, setSel] = useState<[number, number] | null>(null)
  const id = `g-${serie}`
  const valores = dados.map(p => p[serie]).filter((v): v is number => v != null)
  const maxDado = valores.length ? Math.max(...valores) : 1
  // Escala sem eixo Y (como na referência): cabe o dado e os limites próximos dele
  const minDado = valores.length ? Math.min(...valores) : 0
  const visiveis = inverso ? limites : limites.filter(l => l.tipo === 'normal' || l.valor <= maxDado * 2.5)
  const base = inverso ? Math.floor(Math.min(minDado, ...visiveis.map(l => l.valor)) - 4) : 0
  const topo = inverso ? Math.ceil(Math.max(maxDado, ...visiveis.map(l => l.valor)) + 4)
    : Math.max(maxDado * 1.3, ...visiveis.map(l => l.valor * 1.2), 0.001)
  const critico = visiveis.find(l => l.tipo === 'critico')
  // O degradê do SVG é relativo à caixa do próprio traço: a linha vai do menor ao maior dado, a área do maior dado até a base
  const limitar = (v: number) => Math.min(1, Math.max(0, v))
  const corteLinha = critico ? limitar((maxDado - critico.valor) / ((maxDado - minDado) || 1)) : inverso ? 1 : 0
  const corte = critico ? limitar((maxDado - critico.valor) / ((maxDado - base) || 1)) : inverso ? 1 : 0
  const t0 = dados[0]?.t ?? 0, t1 = dados[dados.length - 1]?.t ?? 1
  const ultima = faixas[faixas.length - 1]
  // Marcas redondas no eixo (10:15, 4:00, 12/10…), no máximo 7, alinhadas ao fuso local
  // 30 s a 2 min para os períodos curtos da demonstração (5 e 15 min)
  const passo = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 180, 240, 360, 720, 1440, 2880, 5760, 10080].map(m => m * 60).find(p => (t1 - t0) / p <= 7) ?? 10080 * 60
  const rotuloEixo = passo >= 86400 ? (t: number) => new Date(t * 1000).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
    : passo < 60 ? (t: number) => new Date(t * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : horaCurta
  const fuso = new Date().getTimezoneOffset() * 60
  const marcas: number[] = []
  for (let t = Math.ceil((t0 - fuso) / passo) * passo + fuso; t <= t1; t += passo) marcas.push(t)

  return (
    <div className={`relative ${onZoom ? 'cursor-crosshair select-none' : ''}`}>
      {ultima && (
        // Balão do incidente sobre a faixa, como o "8°C ⟷ 15°C" da referência
        <div className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-md bg-balao px-2.5 py-1.5 text-center shadow-lg"
          style={{ left: `${Math.min(88, Math.max(12, (((ultima.ini + ultima.fim) / 2 - t0) / (t1 - t0)) * 100))}%` }}>
          <div className="flex items-center justify-center gap-1.5 text-[11px] font-semibold text-desastre">
            <WarningCircle size={13} weight="bold" />{ultima.rotulo}
          </div>
          <div className="num mt-0.5 whitespace-nowrap text-[10px] text-tinta-3">{dataHora(ultima.ini).split(' ')[0].replace(',', '')} das {hora(ultima.ini)} às {hora(ultima.fim)}</div>
        </div>
      )}
      <ResponsiveContainer width="100%" height={altura}>
        <AreaChart data={dados} margin={{ top: ultima ? 46 : 18, right: 0, bottom: 0, left: 0 }}
          onMouseDown={onZoom ? e => e?.activeLabel != null && setSel([+e.activeLabel, +e.activeLabel]) : undefined}
          onMouseMove={sel ? e => e?.activeLabel != null && setSel([sel[0], +e.activeLabel]) : undefined}
          onMouseUp={sel ? () => {
            const [a, b] = [Math.min(...sel), Math.max(...sel)]
            setSel(null)
            if (b - a >= Math.max(30, (t1 - t0) / 100)) onZoom?.(a, b) // ignora clique e arrasto minúsculo
          } : undefined}
          onMouseLeave={() => setSel(null)}>
          <defs>
            {/* Acima do limite crítico a linha e a área ficam rosa */}
            <linearGradient id={`${id}-linha`} x1="0" y1="0" x2="0" y2="1">
              <stop offset={corteLinha} stopColor={inverso ? cor : 'var(--color-desastre)'} />
              <stop offset={corteLinha} stopColor={inverso ? 'var(--color-desastre)' : cor} />
            </linearGradient>
            <linearGradient id={`${id}-area`} x1="0" y1="0" x2="0" y2="1">
              {inverso ? <>
                <stop offset={0} stopColor={cor} stopOpacity={0.5} />
                <stop offset={corte} stopColor={cor} stopOpacity={0.2} />
                <stop offset={corte} stopColor="var(--color-desastre)" stopOpacity={0.3} />
                <stop offset={1} stopColor="var(--color-desastre)" stopOpacity={0.08} />
              </> : <>
                <stop offset={0} stopColor="var(--color-desastre)" stopOpacity={0.5} />
                <stop offset={corte} stopColor="var(--color-desastre)" stopOpacity={0.35} />
                <stop offset={corte} stopColor={cor} stopOpacity={0.5} />
                <stop offset={1} stopColor={cor} stopOpacity={0.04} />
              </>}
            </linearGradient>
            <linearGradient id={`${id}-faixa`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-desastre)" stopOpacity={0.55} />
              <stop offset="100%" stopColor="var(--color-desastre)" stopOpacity={0.12} />
            </linearGradient>
          </defs>
          <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={rotuloEixo} ticks={marcas}
            tick={{ fill: 'var(--color-tinta-3)', fontSize: 11 }} tickLine={false} axisLine={{ stroke: 'var(--color-eixo)' }} dy={6} />
          <YAxis hide domain={[base, topo]} />
          {faixas.map(f => (
            <ReferenceArea key={f.ini} x1={f.ini} x2={f.fim} y1={base} y2={topo} fill={`url(#${id}-faixa)`} stroke="var(--color-desastre)" strokeOpacity={0.7} ifOverflow="hidden" />
          ))}
          {visiveis.map(l => (
            <ReferenceLine key={l.rotulo} y={l.valor} stroke={l.tipo === 'critico' ? 'var(--color-limite)' : 'var(--color-normal)'}
              strokeDasharray="6 5" strokeWidth={1}
              label={{ value: `${l.rotulo} : ${fmt(l.valor)} ${unidade}`, position: 'insideTopLeft', fill: 'var(--color-tinta-2)', fontSize: 11, dy: -2 }} />
          ))}
          {sel && sel[0] !== sel[1] && <ReferenceArea x1={sel[0]} x2={sel[1]} y1={base} y2={topo} fill="var(--color-fibra)" fillOpacity={0.14} stroke="var(--color-fibra)" strokeOpacity={0.5} />}
          <Tooltip
            cursor={{ stroke: 'var(--color-fio-forte)' }}
            content={({ active, payload }) => active && payload?.length ? (
              <div className="rounded-md bg-balao px-2.5 py-1.5 text-[11px] shadow-xl">
                <div className="text-tinta-3">{dataHora(payload[0].payload.t)}</div>
                <div className="num mt-0.5 font-semibold" style={{ color: cor }}>
                  {payload[0].value == null ? 'sem resposta' : `${fmt(Number(payload[0].value))} ${unidade}`}
                </div>
              </div>
            ) : null}
          />
          <Area type="monotone" dataKey={serie} stroke={`url(#${id}-linha)`} strokeWidth={1.6} fill={`url(#${id}-area)`}
            connectNulls={false} isAnimationActive={false} dot={false} baseValue={base}
            activeDot={{ r: 3.5, fill: cor, stroke: 'var(--color-painel)', strokeWidth: 2 }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Recorta os trechos sem resposta (null) da série em faixas de incidente. */
export function faixasSemResposta(dados: Ponto[], serie: string, rotulo: string): Faixa[] {
  const out: Faixa[] = []
  let ini: number | null = null
  dados.forEach((p, i) => {
    if (p[serie] == null && ini == null) ini = dados[Math.max(0, i - 1)].t
    if (p[serie] != null && ini != null) { out.push({ ini, fim: p.t, rotulo }); ini = null }
  })
  if (ini != null) out.push({ ini, fim: dados[dados.length - 1].t, rotulo })
  return out
}
