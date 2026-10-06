<p align="center"><img src="docs/logo.svg" width="96" alt=""></p>

# Memcard

**Português** · [English](README.en.md)

Um cartão de memória para o seu PS5: backup automático e versionado dos saves
de um console com jailbreak para um computador da sua rede, com interface web.

![Tela dos cartões: um cartão por perfil, um bloco por jogo](docs/screenshot.png)

*Dados de exemplo. No uso real, cada bloco mostra o ícone do jogo.*

- **Somente leitura no PS5.** Só lista e baixa arquivos pelo FTP do console. Nada é gravado, apagado ou restaurado nele.
- **Todos os perfis**, cada um ligado ou desligado com um toque.
- **Histórico de versões** de cada save, com checksum, para voltar no tempo.
- **Limpeza que não destrói o passado:** versões antigas são rareadas, não zeradas, e passam por uma lixeira.
- **Avisos no Discord sem enxurrada:** uma mensagem por sessão de jogo, editada no lugar.
- **Sem dependências em execução:** só a biblioteca padrão do Python.
- **Interface e avisos em português ou inglês.**

> Este projeto serve para guardar os **seus próprios saves**. Ele não copia jogos
> e não ajuda a desbloquear o console.

## O que você precisa

1. Um PS5 já desbloqueado, com o payload **ftpsrv**
   ([ps5-payload-dev/ftpsrv](https://github.com/ps5-payload-dev/ftpsrv)) rodando
   (porta 2121). A maioria dos pacotes de payloads já o carrega.
2. Um computador sempre ligado na mesma rede (servidor, notebook, mini PC, NAS)
   com **Windows** ou com **Docker** e **Docker Compose**.
3. O IP do PS5 fixo no roteador (reserva de DHCP), para ele não mudar.

Para restaurar um save você também vai querer o
[Garlic SaveMgr](https://git.etawen.dev/earthonion/garlic-savemgr) no PS5.

## Memcard ou Garlic SaveMgr?

Comparação com o [Garlic SaveMgr v1.13](https://git.etawen.dev/earthonion/garlic-savemgr):

| | Garlic SaveMgr v1.13 | Memcard |
|---|---|---|
| Cópia automática | 15 s após fechar o jogo, se o save mudou | Save alterado, PS5 ligou, agenda ou manual; uma versão a cada 10 min durante o jogo |
| Histórico | ZIP por jogo, acumulado sem apagar | Versões por arquivo, com retenção, lixeira e versões fixadas |
| Destino | PS5, USB, FTP simples ou Google Drive (só com o navegador aberto) | Pasta no PC ou servidor |
| Integridade | Sem conferência após a cópia | SHA-256 por versão e conferência semanal |
| Avisos | Na tela do PS5 | Discord por sessão e resumo semanal |

O Garlic sozinho basta se você quer cópias automáticas ao fechar o jogo e um
histórico fora do console, sem retenção nem conferência de integridade.
Se você não precisa de cópias durante o jogo nem de avisos no Discord, pode
ficar com ele, que também é a ferramenta indicada abaixo para restaurar saves.

## Instalação

Primeira vez? Siga o [guia de instalação em 5 minutos](docs/guia.md), com os
caminhos Windows e Docker, a primeira cópia e os avisos no Discord.
Quer entender como o projeto funciona por dentro? Leia a
[arquitetura explicada](docs/arquitetura.md), escrita para quem não programa.

```sh
git clone https://github.com/bps2414/memcard.git
cd memcard
cp config.example.toml config.toml
cp .env.example .env
```

Abra o `config.toml` e troque `host` pelo IP do seu PS5. Se errar ou o IP mudar, o
Memcard procura o PS5 sozinho na rede (IP e porta do FTP) e corrige o arquivo; em
Ajustes há o botão **Procurar agora**. A busca varre o /24 do `host` configurado;
para outra rede, defina `subnet` (ex.: `"192.168.0.0/24"`). Depois:

```sh
docker compose up -d
```

Isso baixa a imagem pronta de `ghcr.io/bps2414/memcard` (amd64 e arm64), publicada
a cada mudança na `main`. O `compose.yml` já traz o **Watchtower**, que a cada 15 min confere se há imagem nova e atualiza
sozinho (para manual, remova esse serviço e use `docker compose pull && docker compose up -d`).
Se preferir construir a partir do código desta pasta, use `docker compose up -d --build`.

Abra `http://<ip-do-computador>:8765`. Com o PS5 ligado e o ftpsrv carregado, a
primeira cópia acontece sozinha em menos de um minuto.

Os backups ficam na pasta `data/`, ao lado do projeto. Para guardar em outro
disco, mude `BACKUP_DIR` no `.env`.

### Windows, sem Docker

1. Baixe `memcard.exe` e `memcard.exe.sha256` na
   [release](https://github.com/bps2414/memcard/releases/latest) e guarde os dois
   numa pasta sua, onde você possa gravar arquivos. Não precisa instalar Python.
2. Confira o SHA-256 no PowerShell, dentro dessa pasta:

   ```powershell
   (Get-FileHash .\memcard.exe -Algorithm SHA256).Hash.ToLower()
   Get-Content .\memcard.exe.sha256
   ```

   O primeiro resultado deve ser igual ao hash no começo do segundo.
3. Abra `memcard.exe` com dois cliques. O executável não tem assinatura digital,
   então o SmartScreen pode mostrar **O Windows protegeu o computador**. Depois
   de conferir o hash, use **Mais informações › Executar assim mesmo**.
4. A interface abre no navegador em `http://127.0.0.1:8765`. Em **Ajustes › Console**,
   confira o IP do PS5 ou use **Procurar agora**. Mantenha a janela do console
   aberta enquanto quiser os backups. Abrir o executável de novo só reabre a interface.

Os ajustes (`config.toml`, criado ao salvar na interface) e a pasta `data/`
ficam ao lado do executável, mesmo quando ele é iniciado por um atalho de outra
pasta. `data/` guarda os saves, o histórico, o registro e o webhook. Para usar
outros caminhos, defina `PS5BACKUP_CONFIG` e `PS5BACKUP_DATA` no ambiente.

No executável, a interface só escuta no próprio PC (`127.0.0.1`). A variável de
ambiente `WEB_BIND` muda esse endereço; `0.0.0.0` permite acesso pela rede local.

Para iniciar com o Windows, crie um atalho para `memcard.exe`, pressione
**Win+R**, digite `shell:startup` e coloque o atalho na pasta que abrir. Ele
inicia depois que você entrar na sua conta do Windows.

**Não há atualização automática no Windows.** Para atualizar, feche o Memcard,
baixe a nova versão, confira o SHA-256 e substitua só o `memcard.exe`, preservando
`config.toml` e `data/`.

### Pelo código-fonte, sem Docker (Windows ou Linux)

Com **Python 3.13**, copie `config.example.toml` para `config.toml` e ajuste o
IP do console. Defina `PS5BACKUP_CONFIG` com o caminho completo desse arquivo e
`PS5BACKUP_DATA` com o caminho completo da pasta dos backups. No PowerShell,
dentro da pasta do projeto:

```powershell
$env:PS5BACKUP_CONFIG = "$PWD/config.toml"
$env:PS5BACKUP_DATA = "$PWD/data"
python -c "import sys; sys.path.insert(0, 'app'); import ps5backup; sys.exit(ps5backup.main())" daemon
```

No Linux, use `export PS5BACKUP_CONFIG="$PWD/config.toml"` e
`export PS5BACKUP_DATA="$PWD/data"` antes do mesmo comando. Abra
`http://localhost:8765`; o terminal precisa ficar aberto enquanto o serviço roda.

## Idioma

A interface segue o idioma do navegador (português ou inglês) e pode ser trocada
em **Ajustes › Idioma**; essa escolha fica guardada no navegador. Os avisos do
Discord usam a chave `language` de `[notify]` (`"pt-BR"` ou `"en"`), que também
aparece em Ajustes. O registro do serviço e a linha de comando ficam em português.

## Usando a interface

**Cartões.** Cada perfil do PS5 é um cartão de memória e cada jogo é um bloco.
O número no bloco é quantos saves aquele jogo tem (um jogo costuma gravar vários
arquivos: perfil, sistema, cada slot). O interruptor do cartão tira ou coloca o
perfil no backup. Clique num bloco para ver os saves do jogo, o histórico de
cada um, baixar, fixar uma versão ou tirar o jogo do backup.

**Ajustes.** Tudo é configurável ali e vale na hora, sem reiniciar: gatilhos,
regras de limpeza, avisos e endereço do console. A interface regrava o
`config.toml`; editar o arquivo à mão também funciona.

**Projeção de espaço.** Abaixo dos cartões, o painel estima quanto os backups
vão ocupar em 30 dias, 90 dias e 1 ano. O cálculo repete o ritmo real de cópias
dos últimos dias e simula cada dia futuro com as suas regras de limpeza.

**Painel.** Um mapa de quando o console foi usado (por hora, nos últimos 14
dias, com filtro por perfil), o tempo de jogo estimado por jogo, o espaço que
cada jogo ocupa e a curva de espaço projetada para 12 meses. O tempo de jogo é
medido pelos momentos em que o jogo gravou saves, então é uma estimativa por
baixo.

**Registro.** Cópias recentes, conferência de integridade e o log do serviço.

## Conferência de integridade

Uma vez por semana o serviço refaz o checksum de todas as versões guardadas e
compara com o que foi anotado na hora da cópia. Não depende do PS5 estar ligado.
Se tudo bate, nada acontece; se alguma versão não bate (disco com defeito,
arquivo apagado por engano), chega um aviso no Discord e a interface mostra
quais são. O intervalo fica em **Ajustes › Quanto guardar** (`verify_interval_days`,
0 desliga), e o botão **Conferir agora** da aba Registro roda na hora.

## Quando a cópia acontece

| Gatilho | O que faz |
|---|---|
| Save alterado | Olha os saves a cada 30 s e copia quando um muda e fica igual por duas leituras seguidas. |
| PS5 ligou | Copia assim que o ftpsrv responde depois do desbloqueio. |
| Agendamento | Conferência completa por intervalo ou em horários fixos, com o PS5 ligado. |
| Manual | Botão **Copiar agora** ou `docker compose exec ps5-backup ps5backup backup`. |

### E quando o PS5 desliga?

Com o console desligado ou em repouso não existe nada rodando nele para ler os
saves, então **não há como fazer backup "ao desligar"**. O que resolve é o
gatilho de save alterado: quando o console cai, a cópia já foi feita. O que for
gravado no último minuto antes de desligar entra na próxima vez que ele ligar.

O jailbreak atual não sobrevive a um desligamento completo. Até você rodar o
desbloqueio de novo, o PS5 aparece como desligado, e isso é esperado.

## Perfis novos

Quando um perfil novo aparece no console, ele segue a regra de
**Ajustes › Perfis e jogos**: entra no backup sozinho (padrão) ou fica de fora
até você decidir. Nos dois casos você é avisado e ele ganha a etiqueta "novo".
Desligar um perfil não apaga as versões que já estavam guardadas.

## Quanto espaço isso ocupa

Alguns jogos regravam o save a cada minuto (medido: ~17 vezes por hora, 6 MB
cada, em 5 arquivos, o que daria uns 500 MB por hora de jogo). Guardar tudo
encheria o disco; apagar por idade deixaria você sem o save de meses atrás. A
solução tem duas etapas.

**Durante o jogo:** a cópia mais recente é sempre guardada, mas só fica uma
versão a cada 10 minutos. As intermediárias são substituídas pela seguinte.
Você não perde nada ao desligar; só deixa de acumular uma versão por minuto.

**Com o tempo:** as versões antigas são rareadas, nunca zeradas.

| Idade da versão | O que fica |
|---|---|
| Última hora | Todas (uma a cada 10 min) |
| Até 2 dias | A última de cada hora |
| Até 14 dias | A última de cada dia |
| Até 12 semanas | A última de cada semana |
| Mais velho que isso | A última de cada mês, sem prazo |

Travas de segurança:

- A limpeza só mexe na pasta de backup. No PS5 nada é apagado nem alterado.
- As 3 versões mais novas de cada save nunca saem.
- Versões **fixadas** nunca saem. Fixe o save de antes de um chefe, de um final, de uma decisão.
- Versões com mais de 2 dias, quando rareadas, vão para `data/trash/` e só são
  apagadas de vez depois de 7 dias. Para recuperar, mova a pasta de volta para o
  mesmo caminho em `data/saves/`.
- Os limites de espaço (tamanho dos backups e espaço livre no disco) **só avisam**. Nunca apagam nada.
- Desligar um perfil ou um jogo, ou o save sumir do console, não apaga nada.

Projeção para um save de 6 MB regravado 17 vezes por hora, 3 horas por dia:

| | Sem limpeza | Com as regras padrão |
|---|---|---|
| 30 dias | 9 GB | 0,26 GB |
| 200 dias | 61 GB | 0,34 GB |

Um jogo com 5 saves assim fica em torno de 1,7 GB enquanto é jogado todo dia, e
encolhe depois que você para de jogar. Comprimir não ajuda: as imagens são
criptografadas (ganho medido de 1 a 2%).

Todos os números são ajustáveis em **Ajustes › Quanto guardar**, que também
mostra quanto cada jogo ocupa e quanto resta no disco.

## Avisos no Discord

Em **Ajustes › Avisos no Discord**, cole a URL de um webhook do seu canal e
toque em **Enviar teste**. Quando o PS5 liga chega uma mensagem, que é editada
em silêncio a cada cópia (o Discord não notifica edições). Quando ele desliga,
ela é trocada por um resumo da sessão: duração, jogos, cópias e espaço total.
São dois avisos por sessão. Falhas repetidas geram no máximo um aviso por hora.
A mensagem mostra como "jogando agora" os jogos que gravaram saves nos últimos
15 minutos; a janela é ajustável.

Toda segunda de manhã chega também um **resumo da semana**: tempo de jogo por
jogo e por perfil, o dia mais jogado e o espaço ocupado. Semana sem jogo não
gera mensagem, e dá para desligar em Ajustes.

O webhook fica em `data/secrets.json`, fora do repositório. Qualquer outra URL
recebe um POST de texto simples (serve para ntfy, por exemplo).

## Restaurar um save

O projeto nunca escreve no PS5. Restaurar é sempre uma ação sua:

1. Na interface, abra o save e baixe a versão desejada.
2. Abra o Garlic SaveMgr (`http://<ip-do-ps5>:8082`), aba **Import**, escolha o
   perfil de destino e envie o arquivo `sdimg_...`.
3. O Garlic compara a conta do save com a do perfil e oferece o resign se for outra.

O save de PS5 é uma imagem criptografada única. Restaurar no mesmo console é o
caso garantido; em outro console não foi verificado.

## Onde ficam os arquivos

```
data/
  saves/<perfil>/<TITLE_ID>/<arquivo>/<data-hora>/<arquivo>    imagem do save
  saves/<perfil>/<TITLE_ID>/<arquivo>/<data-hora>/meta.json    sha256, jogo, perfil, gatilho
  trash/...                                                    versões rareadas, aguardando o prazo
  cache/art/<TITLE_ID>/                                        ícone e arte do jogo
  state.json  backup.log  secrets.json
```

São arquivos comuns: dá para copiar a pasta inteira para outro disco ou nuvem.

## Linha de comando

```sh
docker compose logs -f ps5-backup                          # acompanhar
docker compose exec ps5-backup ps5backup status            # estado
docker compose exec ps5-backup ps5backup diag              # diagnóstico de compatibilidade
docker compose exec ps5-backup ps5backup backup            # copiar agora
docker compose exec ps5-backup ps5backup list              # saves e caminho da última versão
docker compose exec ps5-backup ps5backup verify            # conferir checksums
docker compose exec ps5-backup ps5backup verify --remote   # comparar com o PS5 ao vivo
docker compose exec ps5-backup ps5backup prune             # aplicar a limpeza agora
```

## Segurança

- Por padrão a interface **não tem senha**. No executável, só o próprio PC abre;
  no Docker e no código-fonte, qualquer aparelho da rede local abre.
  Para exigir login, defina `WEB_PASSWORD` no ambiente. No Docker, use o `.env`
  e rode `docker compose up -d`.
  Com a senha definida, tudo pede login: páginas, API e downloads. A sessão dura
  30 dias e cinco senhas erradas seguidas bloqueiam novas tentativas daquele
  aparelho por 5 minutos.
- Mesmo com senha, use só na rede local e não encaminhe a porta 8765 no
  roteador: a conexão é HTTP, sem criptografia.
- O ftpsrv do PS5 também não tem senha e dá acesso de escrita ao console para
  qualquer aparelho da rede. Este projeto só usa os comandos de leitura
  (`CWD`, `MLSD`, `RETR`, além de `FEAT` e `SYST` só no diagnóstico).

## Versões

O histórico de mudanças está em [CHANGELOG.md](CHANGELOG.md) e nas
[Releases](https://github.com/bps2414/memcard/releases). Versionamento semântico.
`ps5backup --version` mostra a instalada.

## Problemas comuns

| Sintoma | O que verificar |
|---|---|
| PS5 não é encontrado sozinho | A busca só vê o bloco `subnet` (ou o /24 do `host`). Ajuste `subnet` ao da sua rede e confira `docker compose logs`. |
| "PS5 desligado" com o console ligado | O desbloqueio foi rodado depois de ligar? O ftpsrv está carregado? Teste `nc -vz <ip-do-ps5> 2121`. |
| Nenhum perfil aparece | Confira o IP em Ajustes › Console e toque em Copiar agora. |
| Jogo aparece só com o ID | O console não tem os metadados dele (comum em jogos de PS4). O backup funciona igual. |
| Save fica "aguardando" por muito tempo | O jogo está regravando sem parar; ele é copiado assim que estabiliza. |

## Como funciona por dentro

A cada ciclo o serviço lista `/user/home/<perfil>/savedata_prospero/<jogo>/`
(e `savedata/` para PS4) pelo FTP, compara tamanho e data com a última leitura,
baixa só o que mudou e confere, relistando, que o arquivo não mudou durante a
cópia. Nomes e artes vêm de `/user/appmeta` e do banco de saves do console.
Testado com ftpsrv v0.21.1 no firmware 13.42.
Veja a [tabela de compatibilidade](docs/COMPATIBILIDADE.md) e como relatar o
resultado de `ps5backup diag` ou `memcard.exe diag` no seu console.

## Próximos passos

Veja o [ROADMAP](ROADMAP.md), incluindo a avaliação de um payload próprio.

## Licença

MIT. Veja [LICENSE](LICENSE).
