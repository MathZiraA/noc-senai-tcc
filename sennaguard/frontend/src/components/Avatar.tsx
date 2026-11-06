import { useState } from 'react'
import { urlFoto } from '../lib/api'

export const iniciais = (nome = '') => nome.split(/[\s-]/).map(p => p[0]).slice(0, 2).join('').toUpperCase()

/** Foto do perfil em círculo; sem foto (ou se ela não carregar), as iniciais. `cor` tinge o círculo das iniciais. */
export default function Avatar({ id, nome, foto, tamanho = 32, cor }: { id: number; nome: string; foto: number | null | undefined; tamanho?: number; cor?: string }) {
  const [falhou, setFalhou] = useState(false)
  const estilo = { width: tamanho, height: tamanho, fontSize: Math.round(tamanho * 0.34) }
  if (foto && !falhou)
    return <img src={urlFoto(id, foto)} alt="" onError={() => setFalhou(true)} style={estilo} className="shrink-0 rounded-full object-cover ring-1 ring-fio-forte" />
  return (
    <div style={{ ...estilo, ...(cor ? { color: cor, background: `color-mix(in srgb, ${cor} 14%, transparent)` } : {}) }}
      className={`grid shrink-0 place-items-center rounded-full font-semibold ${cor ? '' : 'bg-avatar text-white'}`}>
      {iniciais(nome)}
    </div>
  )
}
