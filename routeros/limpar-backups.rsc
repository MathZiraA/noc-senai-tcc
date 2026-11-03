# Backup binário diário dos roteadores em rodízio de 7 arquivos (backup_<lado>_0 a _6): nunca enche a memória.
# Cole o bloco do roteador certo no terminal do WinBox. A última linha apaga os backups antigos com data no nome.

# ---- R-MATRIZ
/system script set [find name="script_backup_automatico"] source=":local d [/system clock get date]; /system backup save name=(\"backup_matriz_\" . ([:tonum [:pick \$d 8 10]] % 7))"
/system script run script_backup_automatico
/file remove [find where name~"^backup_matriz_20"]

# ---- R-FILIAL
/system script set [find name="script_backup_automatico"] source=":local d [/system clock get date]; /system backup save name=(\"backup_filial_\" . ([:tonum [:pick \$d 8 10]] % 7))"
/system script run script_backup_automatico
/file remove [find where name~"^backup_filial_20"]
