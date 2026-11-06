import { useEffect, useRef, useState, type FormEvent } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { ChatCircleDots, PaperPlaneRight, Sparkle, X } from '@phosphor-icons/react'
import { api, useApi } from '../lib/api'
import { useSessao } from '../lib/sessao'

type Msg = { papel: 'usuario' | 'ia'; texto: string; erro?: boolean }

const SUGESTOES_EQUIPE = ['Quanto tempo ficamos no rádio esta semana?', 'Quais alertas estão ativos agora?', 'Algum chamado perto de estourar o SLA?']
const SUGESTOES_CLIENTE = ['A internet da Filial está normal agora?', 'Tem alguma manutenção programada?', 'Como está o meu chamado?']

/** A IA responde em Markdown simples: mostra **negrito** e "* item" como texto formatado, sem os asteriscos. */
function TextoIa({ texto }: { texto: string }) {
  const linhas = texto.replace(/^#{1,6}\s*/gm, '').replace(/^(\s*)[*-]\s+/gm, '$1• ')
  return <>{linhas.split(/(\*\*[^*]+\*\*)/g).map((parte, i) =>
    parte.startsWith('**') && parte.endsWith('**') ? <b key={i} className="font-semibold">{parte.slice(2, -2)}</b> : parte)}</>
}

/** Botão flutuante "Pergunte ao NOC": conversa com a IA usando os dados do Zabbix e do SennaGuard. */
export default function Chat() {
  const { eu } = useSessao()
  const { dados: estado } = useApi<{ provedor: string | null }>('/api/chat/estado')
  const [aberto, setAberto] = useState(false)
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [texto, setTexto] = useState('')
  const [pensando, setPensando] = useState(false)
  const fim = useRef<HTMLDivElement>(null)
  // Com chaves: o Chrome novo devolve uma Promise no scrollIntoView, e o React tentaria chamá-la como limpeza
  useEffect(() => { fim.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, pensando])

  const enviar = async (pergunta: string) => {
    if (!pergunta.trim() || pensando) return
    const nova: Msg[] = [...msgs.filter(m => !m.erro), { papel: 'usuario', texto: pergunta.trim() }]
    setMsgs(nova); setTexto(''); setPensando(true)
    try {
      const r = await api<{ resposta: string }>('/api/chat', { method: 'POST', body: JSON.stringify({ mensagens: nova.slice(-12).map(({ papel, texto }) => ({ papel, texto })) }) })
      setMsgs([...nova, { papel: 'ia', texto: r.resposta }])
    } catch (e) {
      setMsgs([...nova, { papel: 'ia', texto: (e as Error).message, erro: true }])
    } finally { setPensando(false) }
  }
  const sugestoes = eu?.papel === 'Cliente' ? SUGESTOES_CLIENTE : SUGESTOES_EQUIPE

  return (
    <Dialog.Root open={aberto} onOpenChange={setAberto}>
      <Dialog.Trigger aria-label="Pergunte ao NOC" data-tour="chat"
        className="fixed bottom-[calc(76px+env(safe-area-inset-bottom))] right-4 z-30 flex h-12 md:bottom-5 md:right-5 items-center gap-2 rounded-full bg-fibra px-5 font-semibold text-white shadow-[0_8px_24px_rgb(111_90_224/0.35)] transition-transform duration-150 hover:bg-fibra-hover active:scale-[0.97]">
        <ChatCircleDots size={20} weight="fill" /><span className="hidden sm:inline">Pergunte ao NOC</span>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Content
          className="fixed bottom-0 right-0 z-50 flex h-[min(640px,100dvh)] w-full flex-col border border-fio-forte bg-painel shadow-2xl outline-none sm:bottom-5 sm:right-5 sm:w-[400px] sm:rounded-2xl data-[state=open]:animate-[surge-chat_200ms_cubic-bezier(0.23,1,0.32,1)]">
          <header className="flex items-center gap-2.5 border-b border-fio px-5 py-4">
            <span className="grid size-8 place-items-center rounded-full bg-fibra/15 text-fibra"><Sparkle size={16} weight="fill" /></span>
            <div className="leading-tight">
              <Dialog.Title className="font-semibold">Pergunte ao NOC</Dialog.Title>
              <Dialog.Description className="text-[11px] text-tinta-3">
                {estado?.provedor ? `IA (${estado.provedor === 'claude' ? 'Claude' : 'Gemini'}) com os dados do Zabbix, só leitura` : 'IA não configurada no servidor'}
              </Dialog.Description>
            </div>
            <Dialog.Close className="ml-auto grid size-8 place-items-center rounded-lg text-tinta-3 hover:bg-painel-alto hover:text-tinta" aria-label="Fechar"><X size={16} /></Dialog.Close>
          </header>

          <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
            {!msgs.length && (
              <div className="flex flex-col gap-2">
                <p className="text-tinta-2">Pergunte em português sobre a rede, os alertas, os chamados ou as manutenções.</p>
                {sugestoes.map(s => (
                  <button key={s} onClick={() => enviar(s)} disabled={!estado?.provedor}
                    className="rounded-lg border border-fio px-3 py-2 text-left text-[12.5px] text-tinta-2 transition-colors hover:border-fibra/50 hover:text-tinta disabled:opacity-40">{s}</button>
                ))}
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.papel === 'usuario' ? 'justify-end' : ''}`}>
                <div className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 leading-relaxed ${m.papel === 'usuario' ? 'rounded-br-md bg-fibra text-white' : m.erro ? 'rounded-bl-md bg-desastre/10 text-desastre' : 'rounded-bl-md bg-painel-alto text-tinta'}`}>
                  {m.papel === 'ia' ? <TextoIa texto={m.texto} /> : m.texto}
                </div>
              </div>
            ))}
            {pensando && <div className="flex gap-1 px-1 py-2" aria-label="A IA está consultando os dados">{[0, 1, 2].map(i => <span key={i} className="respira size-1.5 rounded-full bg-fibra" style={{ animationDelay: `${i * 0.2}s` }} />)}</div>}
            <div ref={fim} />
          </div>

          <form onSubmit={(e: FormEvent) => { e.preventDefault(); enviar(texto) }} className="flex gap-2 border-t border-fio p-3">
            <input value={texto} onChange={e => setTexto(e.target.value)} maxLength={1000} disabled={!estado?.provedor}
              placeholder={estado?.provedor ? 'Escreva sua pergunta…' : 'IA indisponível'}
              className="h-10 min-w-0 flex-1 rounded-lg border border-fio bg-fenda px-3 text-tinta placeholder:text-tinta-4 focus:border-fibra/60 focus:outline-none" />
            <button type="submit" disabled={!texto.trim() || pensando} aria-label="Enviar"
              className="grid size-10 place-items-center rounded-lg bg-fibra text-white transition-[background-color,transform] hover:bg-fibra-hover active:scale-[0.97] disabled:opacity-40"><PaperPlaneRight size={17} weight="fill" /></button>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
