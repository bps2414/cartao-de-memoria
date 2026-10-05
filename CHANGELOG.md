# Changelog

**Português** · [English](CHANGELOG.en.md)

Segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e
[Versionamento Semântico](https://semver.org/lang/pt-BR/). Enquanto a versão for
`0.x`, uma versão menor (`0.Y.0`) pode mudar chaves do `config.toml`; o que mudar
fica em **Alterado** ou **Removido**. A versão atual também está em `VERSION`, em
`app/ps5backup.py`.

## [Não lançado]

## [0.4.2] - 2026-10-05

### Adicionado
- Roda no Windows a partir do código-fonte, com Python 3.13 e sem Docker;
  instruções nos dois README.
- Testes de backup contra um FTP de PS5 de mentira e matriz de testes no Windows e no Linux.

### Corrigido
- Travamento entre threads e processos no Windows, mantendo `flock` no Linux.
- Config, JSON e log gravados e lidos em UTF-8, preservando nomes como "João".
- Nomes de saves lidos do SQLite com URI válida no Windows e banco fechado antes da limpeza.
- Gravação de JSON tenta novamente no Windows se uma leitura impedir a troca do arquivo.

## [0.4.1] - 2026-10-05

### Alterado
- **Procurar agora** usa o IP e a sub-rede digitados em Ajustes (mesmo sem salvar) e a busca
  também tenta 192.168.1.0/24 e 192.168.0.0/24, então funciona com o endereço vazio ou errado.

### Corrigido
- Trocar o IP ou a porta nos ajustes agora marca o PS5 como offline em até uma sondagem
  (~13 s), em vez de esperar as 3 falhas seguidas (~40 s); a busca automática só roda depois
  de o status atualizar.
- `host` vazio não conecta mais na própria máquina (aparecia como "PS5 ligado em .").

## [0.4.0] - 2026-10-05

### Adicionado
- Busca automática do PS5 na rede: quando o console não responde, o daemon varre a
  sub-rede (portas 2121, 1337 e 21), confirma com FTP anônimo em `/user/home` e
  grava `host` e `ftp_port` no `config.toml`. Repete a cada 5 minutos.
- Botão **Procurar agora** em Ajustes, rota `/api/discover` e comando `ps5backup discover`.
- Chaves `ps5.auto_discover` (padrão `true`) e `ps5.subnet` (vazio = o /24 do `host`).
- Atualização automática: o `compose.yml` traz o Watchtower, que a cada 15 minutos
  baixa a imagem nova da `main` e recria o container.
- `CHANGELOG.md` e versão do app (`VERSION`, `ps5backup --version`, linha de log ao iniciar).

## [0.3.0] - 2026-10-04

### Adicionado
- Imagem pronta no GitHub Container Registry (`ghcr.io/bps2414/memcard`, amd64 e arm64),
  publicada a cada push na `main`.
- Workflow do GitHub Actions que roda os testes.

### Alterado
- O projeto passa a se chamar **Memcard**.

## [0.2.0] - 2026-10-04

### Adicionado
- Resumo semanal no Discord (`notify.weekly_summary`): tempo de jogo por jogo e perfil, e espaço.
- Senha opcional na interface (`WEB_PASSWORD`), cobrindo páginas, API, artes e downloads;
  cinco senhas erradas bloqueiam o endereço por 5 minutos.
- Conferência de integridade agendada (`triggers.verify_interval_days`): refaz o checksum
  das versões guardadas e só avisa se alguma não bater.
- Janela do "jogando agora" configurável (`notify.now_playing_minutes`).
- Interface e avisos em inglês, com `README.en.md` e a chave `notify.language`.
- Testes automáticos (`unittest`) das regras de retenção, da limpeza, da validação do
  config, da projeção e da interface.
- `ROADMAP.md`.

### Alterado
- Discord: mensagem nova quando o PS5 liga e resumo novo quando desliga (editar não
  notifica); a mensagem da sessão mostra o que está sendo jogado agora.
- Quedas rápidas de rede não geram aviso: só vale como desligado após
  `triggers.offline_grace_seconds`.
- Varredura dos saves a cada 30 s, com confirmação em 10 s quando há mudança pendente.

### Corrigido
- `Msg`/`tr` quebravam com erros de configuração que têm o campo `key`.

## [0.1.0] - 2026-10-04

Primeira versão.

### Adicionado
- Backup versionado dos saves do PS5, só leitura, pelo ftpsrv (FTP), com checksum SHA-256 por versão.
- Gatilhos: save alterado, PS5 ligou, agendamento e manual.
- Retenção que rareia versões antigas em vez de apagar por idade, com lixeira, versões
  fixadas, intervalo mínimo por sessão e aviso de espaço.
- Avisos no Discord por sessão de jogo.
- Interface web: cartões por perfil, um bloco por jogo, histórico por save, download,
  ajustes e registro agrupado por sessão.
- Painel: mapa de uso do console, tempo de jogo estimado, espaço por jogo e projeção
  de 12 meses simulada com as regras reais de retenção.

[Não lançado]: https://github.com/bps2414/memcard/compare/v0.4.2...HEAD
[0.4.2]: https://github.com/bps2414/memcard/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/bps2414/memcard/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/bps2414/memcard/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/bps2414/memcard/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/bps2414/memcard/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/bps2414/memcard/releases/tag/v0.1.0
