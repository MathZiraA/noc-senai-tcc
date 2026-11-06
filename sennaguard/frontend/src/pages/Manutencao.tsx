import { useState, type FormEvent } from 'react'
import { CalendarPlus, Wrench } from '@phosphor-icons/react'
import { api, useApi } from '../lib/api'
import { dataHora, duracao } from '../lib/fmt'
import { useSessao } from '../lib/sessao'
import { Botao, Card, Carregando, Vazio } from '../components/ui'

export type Manutencao = { id: number; titulo: string; descricao: string; inicio: number; fim: number; criado_por: string; cancelada_em: number | null }

const DURACOES = [[30, '30 min'], [60, '1 hora'], [120, '2 horas'], [240, '4 horas'], [480, '8 horas']] as const
const campo = 'h-9 w-full rounded-lg border border-fio bg-fenda px-3 text-tinta placeholder:text-tinta-4 focus:border-fibra/60 focus:outline-none'

export function situacao(m: Manutencao, agora = Date.now() / 1000) {
  if (m.cancelada_em) return { texto: 'Cancelada', cor: 'var(--color-tinta-3)' }
  if (m.inicio <= agora && agora < m.fim) return { texto: 'Em andamento', cor: 'var(--color-media)' }
  if (agora < m.inicio) return { texto: `Começa em ${duracao(m.inicio - agora)}`, cor: 'var(--color-fibra)' }
  return { texto: 'Concluída', cor: 'var(--color-led)' }
}

export default function Manutencoes() {
  const { pode } = useSessao()
  const { dados, recarregar } = useApi<Manutencao[]>('/api/manutencoes', 60000, ['manutencao'])
  const amanha = new Date(Date.now() + 86400000); amanha.setHours(8, 0, 0, 0)
  const local = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
  const [f, setF] = useState({ titulo: '', descricao: '', inicio: local(amanha), minutos: 120 })
  const [erro, setErro] = useState('')

  const agendar = async (e: FormEvent) => {
    e.preventDefault(); setErro('')
    const inicio = Math.floor(new Date(f.inicio).getTime() / 1000)
    try {
      await api('/api/manutencoes', { method: 'POST', body: JSON.stringify({ titulo: f.titulo, descricao: f.descricao, inicio, fim: inicio + f.minutos * 60 }) })
      setF({ ...f, titulo: '', descricao: '' }); recarregar()
    } catch (x) { setErro((x as Error).message) }
  }

  return (
    <div className="flex flex-col gap-3">
      <div>
        <h1 className="text-[22px] font-medium tracking-[-0.02em] text-titulo">Manutenção</h1>
        <p className="mt-1 text-tinta-3">Durante a janela, o Zabbix continua medindo, mas os avisos de alerta ficam suspensos. A Filial é avisada no Telegram ao agendar e 1 h antes.</p>
      </div>

      <div className="grid gap-3 lg:grid-cols-[380px_minmax(0,1fr)]">
        {pode('manutencao') && (
          <Card titulo="Agendar janela">
            <form onSubmit={agendar} className="flex flex-col gap-3.5">
              <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">O que será feito
                <input required minLength={4} maxLength={120} value={f.titulo} onChange={e => setF({ ...f, titulo: e.target.value })}
                  placeholder="Ex.: Limpeza do conector da fibra na Filial" className={campo} /></label>
              <div className="grid grid-cols-[minmax(0,1fr)_120px] gap-2">
                <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">Início
                  <input type="datetime-local" required value={f.inicio} onChange={e => setF({ ...f, inicio: e.target.value })} className={campo} /></label>
                <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">Duração
                  <select value={f.minutos} onChange={e => setF({ ...f, minutos: +e.target.value })} className={campo}>
                    {DURACOES.map(([m, r]) => <option key={m} value={m}>{r}</option>)}
                  </select></label>
              </div>
              <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">Aviso para a Filial (opcional)
                <textarea rows={3} maxLength={1000} value={f.descricao} onChange={e => setF({ ...f, descricao: e.target.value })}
                  placeholder="Ex.: a rede pode ficar lenta por alguns minutos enquanto o tráfego passa pelo rádio." className={`${campo} h-auto resize-none py-2`} /></label>
              {erro && <p className="text-[12px] text-desastre">{erro}</p>}
              <Botao type="submit" variante="primario" className="self-end"><CalendarPlus weight="bold" />Agendar e avisar</Botao>
            </form>
          </Card>
        )}

        <Card titulo="Janelas" className={pode('manutencao') ? '' : 'lg:col-span-2'}>
          {!dados ? <Carregando /> : !dados.length ? <Vazio>Nenhuma manutenção nos últimos 30 dias.</Vazio> : (
            <ul className="flex flex-col">
              {[...dados].sort((a, b) => b.inicio - a.inicio).map(m => {
                const s = situacao(m)
                return (
                  <li key={m.id} className={`flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-fio py-3 first:border-0 ${m.cancelada_em ? 'opacity-55' : ''}`}>
                    <Wrench size={18} weight="fill" style={{ color: s.cor }} />
                    <div className="min-w-0 flex-1">
                      <div className="font-medium">{m.titulo}</div>
                      <div className="num text-[11.5px] text-tinta-3">{dataHora(m.inicio)} até {dataHora(m.fim)} · por {m.criado_por}</div>
                      {m.descricao && <div className="mt-1 text-[12px] text-tinta-2">{m.descricao}</div>}
                    </div>
                    <span className="text-[12px] font-semibold" style={{ color: s.cor }}>{s.texto}</span>
                    {pode('manutencao') && !m.cancelada_em && m.fim > Date.now() / 1000 && (
                      <Botao variante="perigo" onClick={() => confirm(`Cancelar "${m.titulo}"? A Filial recebe o aviso de cancelamento.`) && api(`/api/manutencoes/${m.id}`, { method: 'DELETE' }).then(recarregar)}>Cancelar</Botao>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
