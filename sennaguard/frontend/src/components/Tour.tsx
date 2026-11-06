import { useEffect, useLayoutEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useSessao } from '../lib/sessao'
import { Botao } from './ui'

/** `alvo` = valor do atributo data-tour do elemento destacado; sem alvo, o passo aparece no centro da tela. */
type Passo = { alvo?: string; titulo: string; texto: string }

const EQUIPE: Passo[] = [
  { titulo: 'Bem-vindo ao SennaGuard', texto: 'Este é o painel do NOC: o enlace Matriz ⇄ Filial pela fibra e pelo rádio, com os dados do Zabbix em tempo real. Leva menos de um minuto.' },
  { alvo: 'nav', titulo: 'Áreas do NOC', texto: 'Alertas, chamados, equipamentos, manutenções, testes de failover, backups e a base de conhecimento. O ponto colorido avisa quando tem algo pendente.' },
  { alvo: 'latencia', titulo: 'Latência do enlace', texto: 'Alterne entre fibra e rádio. Arraste o mouse sobre o gráfico para dar zoom num trecho; as faixas rosa são os períodos sem resposta.' },
  { alvo: 'periodo', titulo: 'Período', texto: 'De 1 hora a 30 dias, ou um intervalo personalizado. Vale para todos os gráficos da tela.' },
  { alvo: 'editar-painel', titulo: 'Monte a sua Visão', texto: 'Arraste os cartões para mudar a ordem e esconda o que não usa. Fica salvo na sua conta, em qualquer computador.' },
  { alvo: 'sino', titulo: 'Alertas ativos', texto: 'O ponto vermelho aparece quando há alerta sem reconhecimento. Os mais graves também chegam no seu Telegram.' },
  { alvo: 'chat', titulo: 'Pergunte ao NOC', texto: 'Uma IA com acesso só de leitura ao Zabbix: "por que a fibra caiu ontem?", "quanto tempo ficamos no rádio esta semana?".' },
  { alvo: 'perfil', titulo: 'Seu perfil', texto: 'Foto, e-mail, senha e quais avisos chegam no Telegram. O tour pode ser refeito por aqui.' },
]

const CLIENTE: Passo[] = [
  { titulo: 'Bem-vindo ao SennaGuard', texto: 'Aqui você acompanha a rede da Filial e fala com o NOC da Matriz. Leva menos de um minuto.' },
  { alvo: 'latencia', titulo: 'Como está a rede', texto: 'A latência mostra a qualidade da ligação com a Matriz. Faixas rosa são os momentos em que ela caiu.' },
  { alvo: 'chamados', titulo: 'Seus chamados', texto: 'Algo não funciona? Abra um chamado: o NOC recebe na hora e você acompanha cada resposta por aqui.' },
  { alvo: 'chat', titulo: 'Pergunte ao NOC', texto: 'Tire dúvidas rápidas com a IA do NOC antes de abrir um chamado.' },
  { alvo: 'perfil', titulo: 'Seu perfil', texto: 'Foto, e-mail, senha e os avisos no Telegram. O tour pode ser refeito por aqui.' },
]

/** Primeiro elemento com aquele data-tour que está visível (o menu lateral some no celular, a barra inferior no PC). */
function achar(alvo: string) {
  return [...document.querySelectorAll<HTMLElement>(`[data-tour="${alvo}"]`)].find(e => e.getClientRects().length > 0) ?? null
}

export default function Tour({ aberto, onFim }: { aberto: boolean; onFim: () => void }) {
  const { eu, recarregar } = useSessao()
  const ir = useNavigate()
  const passos = eu?.papel === 'Cliente' ? CLIENTE : EQUIPE
  const [i, setI] = useState(0)
  const [caixa, setCaixa] = useState<DOMRect | null>(null)
  const p = passos[i]

  useEffect(() => { if (aberto) { setI(0); ir('/') } }, [aberto, ir])
  useLayoutEffect(() => {
    if (!aberto) return
    const medir = () => setCaixa(p.alvo ? achar(p.alvo)?.getBoundingClientRect() ?? null : null)
    if (p.alvo) achar(p.alvo)?.scrollIntoView({ block: 'nearest' })
    const t = setTimeout(medir, 80) // espera a Visão desenhar os cartões
    window.addEventListener('resize', medir); window.addEventListener('scroll', medir, true)
    return () => { clearTimeout(t); window.removeEventListener('resize', medir); window.removeEventListener('scroll', medir, true) }
  }, [aberto, p])
  useEffect(() => {
    if (!aberto) return
    const tecla = (e: KeyboardEvent) => { if (e.key === 'Escape') fim(); if (e.key === 'ArrowRight') avancar(); if (e.key === 'ArrowLeft') setI(x => Math.max(0, x - 1)) }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  })
  if (!aberto) return null

  const fim = () => { onFim(); if (!eu?.tour_visto) api('/api/eu/tour', { method: 'POST' }).then(recarregar) }
  const avancar = () => (i < passos.length - 1 ? setI(i + 1) : fim())
  const folga = 6
  // Balão abaixo do alvo quando cabe; senão acima. Sem alvo visível, centralizado.
  const largura = Math.min(340, window.innerWidth - 32)
  const embaixo = caixa && caixa.bottom + 190 < window.innerHeight
  const estilo: React.CSSProperties = caixa
    ? { left: Math.min(Math.max(16, caixa.left), window.innerWidth - largura - 16), width: largura, ...(embaixo ? { top: caixa.bottom + folga + 10 } : { bottom: window.innerHeight - caixa.top + folga + 10 }) }
    : { left: '50%', top: '50%', width: largura, transform: 'translate(-50%, -50%)' }

  return (
    <div className="fixed inset-0 z-[60]" role="dialog" aria-modal="true" aria-labelledby="tour-titulo">
      {caixa
        ? <div className="pointer-events-none absolute rounded-xl ring-2 ring-fibra transition-all duration-200"
            style={{ left: caixa.left - folga, top: caixa.top - folga, width: caixa.width + folga * 2, height: caixa.height + folga * 2, boxShadow: '0 0 0 9999px rgb(0 0 0 / 0.62)' }} />
        : <div className="absolute inset-0 bg-black/62" />}
      <div className="absolute rounded-xl border border-fio-forte bg-painel-alto p-5 shadow-2xl animate-[surge_200ms_cubic-bezier(0.23,1,0.32,1)]" style={estilo}>
        <div className="num text-[11px] font-medium text-fibra">{i + 1} de {passos.length}</div>
        <h2 id="tour-titulo" className="mt-1 text-[15px] font-semibold">{p.titulo}</h2>
        <p className="mt-1.5 leading-relaxed text-tinta-2">{p.texto}</p>
        <div className="mt-4 flex items-center gap-2">
          <button onClick={fim} className="text-[12px] text-tinta-3 hover:text-tinta">Pular tour</button>
          <div className="ml-auto flex gap-2">
            {i > 0 && <Botao onClick={() => setI(i - 1)}>Voltar</Botao>}
            <Botao variante="primario" onClick={avancar} autoFocus>{i < passos.length - 1 ? 'Próximo' : 'Concluir'}</Botao>
          </div>
        </div>
      </div>
    </div>
  )
}
