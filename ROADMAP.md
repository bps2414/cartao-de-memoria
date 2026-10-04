# Roadmap

O que está planejado, em ordem de prioridade. Nada aqui tem data. A regra do
projeto continua a mesma: **o que já funciona é somente leitura no PS5**, e
qualquer coisa que escreva no console entra desligada por padrão.

## Feito

- Cópia versionada de todos os perfis, só leitura, pelo ftpsrv.
- Gatilhos: save alterado, PS5 ligou, agendamento, manual.
- Interface web: cartões por perfil, histórico por save, ajustes, registro.
- Limpeza segura: intervalo mínimo por sessão, rareamento, lixeira, versões fixadas.
- Painel: mapa de uso, tempo de jogo estimado, espaço por jogo, projeção de 12 meses.
- Avisos no Discord por sessão (liga, atualizações silenciosas, resumo ao desligar).
- Interface e avisos em inglês, com dicionário pt-BR/en e README.en.md.
- Testes automáticos (unittest) das regras de retenção, da limpeza, da validação
  do config, da projeção e da senha.
- Conferência de integridade agendada: `verify` sozinho uma vez por semana, com
  aviso só se alguma versão não bater.
- Janela do "jogando agora" configurável.
- Senha opcional na interface (`WEB_PASSWORD`), cobrindo API e downloads.
- Resumo semanal no Discord: tempo de jogo por jogo e perfil, e espaço.
- Imagem pronta no GitHub Container Registry, publicada a cada push na `main`.

## Próximo

1. **Restauração validada.** Roteiro testado de restaurar um save pelo Garlic
   SaveMgr, com prints, incluindo o caso de outro perfil (resign). Hoje o
   procedimento está descrito, mas não foi exercitado de ponta a ponta.
2. **Segunda cópia.** Espelhar a pasta de backup para outro disco ou nuvem
   (rclone ou restic), já que hoje o histórico vive em um disco só.

## Depois

- **Restaurar pelo painel.** Botão "Restaurar no PS5" usando a API do Garlic
  SaveMgr. Desligado por padrão; antes de sobrescrever, copia e fixa o save
  atual; depois confere se o que ficou no console é a versão escolhida.
- **Saves de PS4** validados em console real (o código já copia `savedata/`
  com a chave `.bin`, mas não foi testado).
- **Deduplicação por blocos, opcional.** Versões seguidas do mesmo save
  compartilham cerca de 80% dos blocos. Reduziria o espaço em 4 a 5 vezes, ao
  custo de as versões deixarem de ser arquivos comuns. Só se o espaço virar
  problema de verdade.
- **Mais de um console** no mesmo servidor.
- **Registro técnico e linha de comando em inglês.** Hoje só a interface e os
  avisos são traduzidos; o `backup.log` e o `ps5backup` continuam em português.

## Explorar: um payload próprio

Hoje o serviço descobre tudo de fora, perguntando ao FTP a cada 30 segundos.
Um payload pequeno rodando no PS5 poderia **avisar** em vez de ser consultado.

O que ele traria:

- **Jogo aberto e fechado na hora.** O sistema do PS5 expõe o título em
  execução (é assim que o Garlic SaveMgr detecta o fechamento de jogo). A cópia
  aconteceria no momento exato em que o jogo fecha, sem esperar a varredura.
- **"Jogando agora" e tempo de jogo exatos,** em vez da estimativa pelos
  momentos em que o save foi gravado.
- **Aviso antes de dormir.** Se der para interceptar a entrada em repouso, a
  última cópia sairia antes de a rede cair. Isso é uma hipótese a testar, não
  uma promessa; no desligamento pela energia não há o que fazer.
- **Menos dependência do ftpsrv,** que ignora o caminho no `MLSD` e exigiu um
  desvio no código.

O que ele custa:

- Código C com o PS5 Payload SDK, rodando com privilégios de kernel no console.
  Um erro ali trava o PS5; um erro no serviço atual só perde uma cópia.
- Precisa ser recarregado a cada desbloqueio e acompanhar mudanças de firmware.
- Quebra a promessa mais forte do projeto hoje: não instalar nada novo no PS5.

**Veredito:** útil, mas não agora. O ganho real é de precisão (segundos em vez
de até um minuto) e de dados mais exatos no painel, não de segurança dos saves,
que já estão cobertos. Se for feito, será:

- **só de leitura e de aviso:** informa eventos por HTTP para o servidor, nunca
  escreve em saves;
- **opcional:** tudo continua funcionando sem ele, pelo caminho atual;
- **pequeno e auditável:** um arquivo, sem rede para fora da LAN.

O caminho de menor risco para chegar lá é primeiro usar o que o Garlic SaveMgr
já expõe (`/api/cloud/auto_status` informa o título em execução quando o
auto-backup dele está ligado) e só escrever um payload se isso não bastar.

## Fora de escopo

- Copiar, instalar ou distribuir jogos.
- Qualquer coisa relacionada ao desbloqueio do console.
- Expor a interface na internet.
