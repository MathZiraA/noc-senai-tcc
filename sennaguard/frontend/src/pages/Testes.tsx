import { useState, type FormEvent } from 'react'
import { CheckCircle, FilePdf, Flask, XCircle } from '@phosphor-icons/react'
import { api, useApi } from '../lib/api'
import { dataHora } from '../lib/fmt'
import { useSessao } from '../lib/sessao'
import { Botao, Card, Carregando, Vazio } from '../components/ui'

type Teste = {
  id: number; pedido_por: number; pedido_por_nome: string; motivo: string; agendado_para: number | null; status: string
  decidido_por: string | null; inicio: number | null; fim: number | null; criado_em: number
  resultado: { ida_s: number; volta_s: number; aprovado: boolean; quedas: [number, number][]; duracao_s: number; filial_respondendo_no_fim: boolean; erro?: string } | null
}

const STATUS: Record<string, { rotulo: string; cor: string }> = {
  pendente: { rotulo: 'Aguardando aprovação', cor: 'var(--color-media)' },
  aprovado: { rotulo: 'Aprovado, na fila', cor: 'var(--color-fibra)' },
  executando: { rotulo: 'Executando agora', cor: 'var(--color-alta)' },
  concluido: { rotulo: 'Concluído', cor: 'var(--color-led)' },
  recusado: { rotulo: 'Recusado', cor: 'var(--color-tinta-3)' },
  cancelado: { rotulo: 'Cancelado', cor: 'var(--color-tinta-3)' },
  falhou: { rotulo: 'Falhou', cor: 'var(--color-desastre)' },
}
const campo = 'h-9 w-full rounded-lg border border-fio bg-fenda px-3 text-tinta placeholder:text-tinta-4 focus:border-fibra/60 focus:outline-none'

export default function Testes() {
  const { pode, eu } = useSessao()
  const { dados, recarregar } = useApi<Teste[]>('/api/testes', 10000, ['testes'])
  const [motivo, setMotivo] = useState('Teste semanal da redundância')
  const [quando, setQuando] = useState('')
  const [erro, setErro] = useState('')

  const pedir = async (e: FormEvent) => {
    e.preventDefault(); setErro('')
    try {
      await api('/api/testes', { method: 'POST', body: JSON.stringify({ motivo, agendado_para: quando ? Math.floor(new Date(quando).getTime() / 1000) : null }) })
      setQuando(''); recarregar()
    } catch (x) { setErro((x as Error).message) }
  }
  const acao = (id: number, a: string) => api(`/api/testes/${id}/${a}`, { method: 'POST' }).then(recarregar).catch(e => alert(e.message))

  return (
    <div className="flex flex-col gap-3">
      <div>
        <h1 className="text-[22px] font-medium tracking-[-0.02em] text-titulo">Testes de failover</h1>
        <p className="mt-1 text-tinta-3">A fibra (sfp1) é desligada no R-MATRIZ por 60 s e o SennaGuard mede quanto tempo a Filial fica sem resposta. Cada teste precisa da aprovação de um administrador.</p>
      </div>

      <div className="grid gap-3 lg:grid-cols-[360px_minmax(0,1fr)]">
        <Card titulo="Pedir teste">
          <form onSubmit={pedir} className="flex flex-col gap-3.5">
            <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">Motivo
              <input required minLength={4} maxLength={300} value={motivo} onChange={e => setMotivo(e.target.value)} className={campo} /></label>
            <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">Quando (vazio = logo após a aprovação)
              <input type="datetime-local" value={quando} onChange={e => setQuando(e.target.value)} className={campo} /></label>
            <p className="rounded-lg bg-media/10 px-3 py-2 text-[12px] leading-relaxed text-tinta-2">
              Durante o teste a Filial passa a usar o rádio. Se a manutenção estiver marcada para o mesmo horário, os avisos de alerta ficam suspensos.
            </p>
            {erro && <p className="text-[12px] text-desastre">{erro}</p>}
            <Botao type="submit" variante="primario" className="self-end"><Flask weight="fill" />Pedir aprovação</Botao>
          </form>
        </Card>

        <Card titulo="Histórico">
          {!dados ? <Carregando /> : !dados.length ? <Vazio>Nenhum teste ainda.</Vazio> : (
            <ul className="flex flex-col">
              {dados.map(t => {
                const s = STATUS[t.status]
                const r = t.resultado
                return (
                  <li key={t.id} className="flex flex-col gap-3 border-t border-fio py-4 first:border-0 first:pt-0">
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                      <span className="font-mono text-[12px] text-tinta-3">#{t.id}</span>
                      <div className="min-w-0 flex-1">
                        <div className="font-medium">{t.motivo}</div>
                        <div className="num text-[11.5px] text-tinta-3">
                          pedido por {t.pedido_por_nome} · {t.agendado_para ? `agendado para ${dataHora(t.agendado_para)}` : 'assim que aprovado'}
                          {t.decidido_por && ` · ${t.status === 'recusado' ? 'recusado' : 'aprovado'} por ${t.decidido_por}`}
                        </div>
                      </div>
                      <span className={`flex items-center gap-1.5 text-[12px] font-semibold ${t.status === 'executando' ? 'respira' : ''}`} style={{ color: s.cor }}>
                        <span className="size-1.5 rounded-full bg-current" />{s.rotulo}
                      </span>
                      {t.status === 'pendente' && pode('aprovar_teste') && <>
                        <Botao variante="primario" onClick={() => confirm('Aprovar? A fibra será desligada por 60 s no horário do teste.') && acao(t.id, 'aprovar')}><CheckCircle weight="fill" />Aprovar</Botao>
                        <Botao onClick={() => acao(t.id, 'recusar')}><XCircle />Recusar</Botao>
                      </>}
                      {['pendente', 'aprovado'].includes(t.status) && (t.pedido_por === eu?.id || pode('aprovar_teste')) &&
                        <Botao variante="perigo" onClick={() => acao(t.id, 'cancelar')}>Cancelar</Botao>}
                    </div>
                    {r && !r.erro && <Laudo t={t} />}
                    {r?.erro && <p className="rounded-lg bg-desastre/10 px-3 py-2 text-[12px] text-desastre">{r.erro}</p>}
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

/** Resultado do teste: os dois números que importam e a régua com os trechos sem resposta. */
function Laudo({ t }: { t: Teste }) {
  const r = t.resultado!
  const total = r.duracao_s + 40
  return (
    <div className="rounded-xl border border-fio bg-fenda px-4 py-3.5">
      <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
        <div>
          <div className="text-[11px] text-tinta-3">Resultado</div>
          <div className={`text-[16px] font-semibold ${r.aprovado ? 'text-led' : 'text-desastre'}`}>{r.aprovado ? 'Aprovado' : 'Reprovado'}</div>
        </div>
        <div><div className="text-[11px] text-tinta-3">Fibra → rádio</div><div className="num text-[16px] font-semibold">{r.ida_s.toLocaleString('pt-BR')} s</div></div>
        <div><div className="text-[11px] text-tinta-3">Rádio → fibra</div><div className="num text-[16px] font-semibold">{r.volta_s ? `${r.volta_s.toLocaleString('pt-BR')} s` : 'sem perda'}</div></div>
        <a className="ml-auto" href={`${import.meta.env.BASE_URL}api/testes/${t.id}/laudo.pdf`}><Botao><FilePdf weight="fill" />Laudo em PDF</Botao></a>
      </div>
      <div className="relative mt-4 h-3 overflow-hidden rounded-full bg-led/25" role="img" aria-label="Linha do tempo do teste: trechos vermelhos sem resposta">
        <span className="absolute inset-y-0 bg-radio/40" style={{ left: 0, width: `${(r.duracao_s / total) * 100}%` }} title="fibra desligada: tráfego pelo rádio" />
        {r.quedas.map(([ini, dur]) => <span key={ini} className="absolute inset-y-0 min-w-[3px] bg-desastre" style={{ left: `${(ini / total) * 100}%`, width: `${(dur / total) * 100}%` }} />)}
      </div>
      <div className="num mt-1.5 flex justify-between text-[10.5px] text-tinta-3">
        <span>0 s · fibra desligada</span><span>{r.duracao_s} s · fibra religada</span><span>{total} s</span>
      </div>
    </div>
  )
}
