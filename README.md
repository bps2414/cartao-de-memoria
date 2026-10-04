# Cartão de Memória

Backup automático e versionado dos saves de um PS5 com jailbreak para um
computador da sua rede, com interface web.

![Tela dos cartões: um cartão por perfil, um bloco por save](docs/screenshot.png)

*Dados de exemplo. No uso real, cada bloco mostra o ícone do jogo.*

- **Somente leitura no PS5.** Só lista e baixa arquivos pelo FTP do console. Nada é gravado, apagado ou restaurado nele.
- **Todos os perfis**, cada um ligado ou desligado com um toque.
- **Histórico de versões** de cada save, com checksum, para voltar no tempo.
- **Limpeza que não destrói o passado:** versões antigas são rareadas, não zeradas, e passam por uma lixeira.
- **Avisos no Discord sem enxurrada:** uma mensagem por sessão de jogo, editada no lugar.
- **Sem dependências:** um container Python só com a biblioteca padrão.

> Este projeto serve para guardar os **seus próprios saves**. Ele não copia jogos
> e não ajuda a desbloquear o console.

## O que você precisa

1. Um PS5 já desbloqueado, com o payload **ftpsrv**
   ([ps5-payload-dev/ftpsrv](https://github.com/ps5-payload-dev/ftpsrv)) rodando
   (porta 2121). A maioria dos pacotes de payloads já o carrega.
2. Um computador sempre ligado na mesma rede (servidor, notebook, mini PC, NAS)
   com **Docker** e **Docker Compose**.
3. O IP do PS5 fixo no roteador (reserva de DHCP), para ele não mudar.

Para restaurar um save você também vai querer o
[Garlic SaveMgr](https://git.etawen.dev/earthonion/garlic-savemgr) no PS5.

## Instalação

```sh
git clone https://github.com/bps2414/ps5-save-backup.git
cd ps5-save-backup
cp config.example.toml config.toml
cp .env.example .env
```

Abra o `config.toml` e troque `host` pelo IP do seu PS5. Depois:

```sh
docker compose up -d --build
```

Abra `http://<ip-do-computador>:8765`. Com o PS5 ligado e o ftpsrv carregado, a
primeira cópia acontece sozinha em menos de um minuto.

Os backups ficam na pasta `data/`, ao lado do projeto. Para guardar em outro
disco, mude `BACKUP_DIR` no `.env`.

## Usando a interface

**Cartões.** Cada perfil do PS5 é um cartão de memória e cada save é um bloco.
O número no bloco é quantas versões estão guardadas. O interruptor do cartão
tira ou coloca o perfil no backup. Clique num bloco para ver as versões, baixar,
fixar uma versão ou tirar aquele jogo do backup.

**Ajustes.** Tudo é configurável ali e vale na hora, sem reiniciar: gatilhos,
regras de limpeza, avisos e endereço do console. A interface regrava o
`config.toml`; editar o arquivo à mão também funciona.

**Registro.** Cópias recentes, conferência de integridade e o log do serviço.

## Quando a cópia acontece

| Gatilho | O que faz |
|---|---|
| Save alterado | Olha os saves a cada 60 s e copia quando um muda e fica igual por duas leituras seguidas. |
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

Alguns jogos regravam o save a cada minuto. Guardar tudo para sempre encheria o
disco; apagar por idade deixaria você sem o save de meses atrás. Por isso as
versões antigas são **rareadas**:

| Idade da versão | O que fica |
|---|---|
| Última hora | Todas |
| Até 2 dias | A última de cada hora |
| Até 14 dias | A última de cada dia |
| Até 12 semanas | A última de cada semana |
| Mais velho que isso | A última de cada mês, sem prazo |

Travas de segurança:

- As 3 versões mais novas de cada save nunca saem.
- Versões **fixadas** nunca saem. Fixe o save de antes de um chefe, de um final, de uma decisão.
- O que sai vai para `data/trash/` e só é apagado de vez depois de 7 dias. Para
  recuperar, mova a pasta de volta para o mesmo caminho em `data/saves/`.
- O limite de espaço **só avisa**. Passar dele nunca apaga nada.
- Desligar um perfil ou um jogo, ou o save sumir do console, não apaga nada.

Numa simulação de um save de 6 MB regravado a cada minuto, 3 horas por dia,
durante 200 dias: 36.000 versões (211 GB) viram 98 versões (0,6 GB).

Todos os números da tabela são ajustáveis, e a limpeza pode ser desligada.

## Avisos no Discord

Em **Ajustes › Avisos no Discord**, cole a URL de um webhook do seu canal e
toque em **Enviar teste**. Cada sessão de jogo vira uma única mensagem, que é
editada a cada cópia e fechada quando o PS5 desliga. Falhas repetidas geram no
máximo um aviso por hora.

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
docker compose exec ps5-backup ps5backup backup            # copiar agora
docker compose exec ps5-backup ps5backup list              # saves e caminho da última versão
docker compose exec ps5-backup ps5backup verify            # conferir checksums
docker compose exec ps5-backup ps5backup verify --remote   # comparar com o PS5 ao vivo
docker compose exec ps5-backup ps5backup prune             # aplicar a limpeza agora
```

## Segurança

- A interface **não tem senha**. Use só na rede local e não encaminhe a porta
  8765 no roteador.
- O ftpsrv do PS5 também não tem senha e dá acesso de escrita ao console para
  qualquer aparelho da rede. Este projeto só usa os comandos de leitura
  (`CWD`, `MLSD`, `RETR`).

## Problemas comuns

| Sintoma | O que verificar |
|---|---|
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

## Licença

MIT. Veja [LICENSE](LICENSE).
