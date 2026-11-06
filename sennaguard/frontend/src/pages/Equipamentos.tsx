import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Antenna, Network, Router, Server } from 'lucide-react'
import { useApi, type Equipamento, type Ponto, type Visao } from '../lib/api'
import { duracao, ms } from '../lib/fmt'
import Trilho from '../components/Trilho'
import Grafico from '../components/Grafico'
import Modal from '../components/Modal'
import { Card, Carregando, Chip, Led } from '../components/ui'

const icones = { roteador: Router, switch: Network, antena: Antenna, servidor: Server } as const

type Detalhe = Equipamento & {
  recursos: { cpu?: number | null; memoria?: number | null; uptime?: number | null; routeros?: string; ccq?: number; distancia_m?: number; frequencia?: string } | null
  interfaces: { nome: string; papel: string; up: boolean | null; rx: number | null; tx: number | null }[]
}

// Faixa do sinal do noc.conf: abaixo de -60 dBm é crítico; a bancada mediu -53/-52 dBm
const LIMITES_SINAL = [{ valor: -60, rotulo: 'Crítico', tipo: 'critico' as const }, { valor: -53, rotulo: 'Normal', tipo: 'normal' as const }]

export default function Equipamentos() {
  const { dados } = useApi<Equipamento[]>('/api/equipamentos', 10000, ['visao'])
  const { dados: v } = useApi<Visao>('/api/visao', 10000, ['visao'])
  const { dados: sinal } = useApi<Ponto[]>('/api/serie/sinal?horas=24', 60000)
  const [lado, setLado] = useState<'filial' | 'matriz'>('filial')
  const [params, setParams] = useSearchParams()
  const aberto = params.get('host')
  if (!dados) return <Carregando />
  const locais = [...new Set(dados.map(e => e.local || 'Sem local'))]
  const fora = dados.filter(e => !e.up).length
  const ultimo = sinal?.length ? sinal[sinal.length - 1][lado] : null
  const abrir = (nome: string) => setParams({ host: nome })

  return (
    <div className="flex flex-col gap-3">
      <div>
        <h1 className="text-[22px] font-medium tracking-[-0.02em] text-titulo">Equipamentos</h1>
        <p className="mt-1 text-tinta-3">
          {dados.length} hosts monitorados · {fora ? <span className="font-medium text-desastre">{fora} sem resposta</span> : 'todos respondendo'}
          {' '}· clique num equipamento para ver interfaces e recursos
        </p>
      </div>
      {v && <Trilho v={v} onNo={abrir} />}

      <Card className="md:!px-9 md:!pt-7 !pb-5" titulo="Sinal do rádio"
        extra={<span className="flex items-baseline gap-2">
          <span className="num text-[17px] font-semibold" style={{ color: ultimo == null ? 'var(--color-desastre)' : 'var(--color-radio)' }}>
            {ultimo == null ? 'sem leitura' : `${ultimo.toLocaleString('pt-BR')} dBm`}</span>
          <span className="text-[10.5px] text-tinta-3">antena {lado === 'filial' ? 'da Filial' : 'da Matriz'} · bom entre -60 e -50 dBm</span>
        </span>}
        acao={<div className="flex gap-1.5">
          <Chip ativo={lado === 'filial'} onClick={() => setLado('filial')}>Filial</Chip>
          <Chip ativo={lado === 'matriz'} onClick={() => setLado('matriz')}>Matriz</Chip>
        </div>}>
        {sinal ? <Grafico dados={sinal} serie={lado} cor="var(--color-radio)" unidade="dBm" altura={170} inverso limites={LIMITES_SINAL} />
          : <div className="h-[170px]" />}
      </Card>

      <div className="grid gap-3 lg:grid-cols-2">
        {locais.map(local => (
          <Card key={local} titulo={local} extra={<span className="text-[11px] text-tinta-3">{local === 'Matriz' ? '192.168.10.0/24' : local === 'Filial' ? '192.168.20.0/24' : ''}</span>}>
            <ul className="flex flex-col gap-1">
              {dados.filter(e => (e.local || 'Sem local') === local).map(e => {
                const Icone = icones[e.tipo as keyof typeof icones] ?? Server
                return (
                  <li key={e.nome}>
                    <button onClick={() => abrir(e.nome)}
                      className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-pilula-hover ${e.up ? '' : 'bg-desastre/[0.07]'}`}>
                      <div className={`grid size-8 place-items-center rounded-lg ${e.up ? 'bg-painel-alto text-tinta-2' : 'bg-desastre/15 text-desastre'}`}><Icone className="size-4" strokeWidth={1.7} /></div>
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold">{e.nome}</div>
                        <div className="truncate text-[11px] text-tinta-3"><span className="font-mono">{e.ip}</span> · {e.modelo}</div>
                      </div>
                      {e.sinal != null && <span className="num font-mono text-[12px] text-radio">{e.sinal} dBm</span>}
                      <span className="num hidden w-16 text-right font-mono text-[12px] text-tinta-2 sm:block">{e.up ? ms(e.latencia) : ''}</span>
                      <span className="flex w-24 items-center justify-end gap-1.5 text-[12px] font-medium">
                        <Led cor={e.up ? 'var(--color-led)' : 'var(--color-desastre)'} pulsa={!e.up} />{e.up ? 'Respondendo' : 'Sem resposta'}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </Card>
        ))}
      </div>

      <Modal lado aberto={!!aberto} onClose={() => setParams({})} titulo={aberto} descricao="Dados do Zabbix (SNMP)">
        {aberto && <FichaEquipamento nome={aberto} />}
      </Modal>
    </div>
  )
}

function FichaEquipamento({ nome }: { nome: string }) {
  const { dados: d, erro } = useApi<Detalhe>(`/api/equipamentos/${encodeURIComponent(nome)}`, 10000)
  if (erro) return <p className="text-desastre">{erro}</p>
  if (!d) return <Carregando />
  const r = d.recursos
  const numeros = (r ? [
    ['CPU', r.cpu != null ? `${r.cpu}%` : null], ['Memória', r.memoria != null ? `${r.memoria}%` : null],
    ['No ar há', r.uptime ? duracao(r.uptime) : null], ['RouterOS', r.routeros ?? null],
    ['Sinal', d.sinal != null ? `${d.sinal} dBm` : null], ['CCQ', r.ccq != null ? `${r.ccq}%` : null],
    ['Distância', r.distancia_m ? `${r.distancia_m} m` : null], ['Frequência', r.frequencia ?? null],
  ] : []).filter((x): x is [string, string] => !!x[1])
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-2 text-[12px] text-tinta-2">
        <Led cor={d.up ? 'var(--color-led)' : 'var(--color-desastre)'} pulsa={!d.up} />{d.up ? 'Respondendo' : 'Sem resposta'}
        <span className="font-mono text-tinta-3">· {d.ip}</span>{d.modelo && <span className="text-tinta-3">· {d.modelo}</span>}
      </div>
      {numeros.length > 0 && (
        <dl className="grid grid-cols-2 gap-3">
          {numeros.map(([k, v]) => (
            <div key={k} className="rounded-lg bg-painel-alto px-3.5 py-2.5">
              <dt className="text-[11px] text-tinta-3">{k}</dt><dd className="num mt-0.5 text-[16px] font-semibold">{v}</dd>
            </div>
          ))}
        </dl>
      )}
      {!r && !d.up && <p className="text-tinta-3">O equipamento não responde: sem dados de recursos agora.</p>}
      {d.interfaces.length > 0 && (
        <section>
          <h3 className="mb-2 text-[13px] font-semibold">Interfaces</h3>
          <ul className="flex flex-col">
            {d.interfaces.map(i => (
              <li key={i.nome} className="grid grid-cols-[14px_minmax(0,1fr)_auto] items-center gap-3 border-t border-fio py-2.5">
                <Led cor={i.up ? 'var(--color-led)' : 'var(--color-tinta-4)'} />
                <div className="min-w-0">
                  <div className="truncate font-mono text-[12px] font-medium">{i.nome}</div>
                  {i.papel && <div className="text-[11px] text-tinta-3">{i.papel}</div>}
                </div>
                <div className="num text-right text-[11.5px] text-tinta-2">
                  {i.up ? <>↓ {i.rx ?? '—'} · ↑ {i.tx ?? '—'} <span className="text-tinta-3">Mbps</span></> : <span className="text-tinta-3">sem link</span>}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
