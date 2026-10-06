# Memcard: instalação em 5 minutos

Comece com o console desbloqueado, com o payload **ftpsrv carregado**.
O Memcard copia seus saves para o computador e guarda um histórico de versões.
Ele só lê arquivos do PS5. Este guia não ensina a desbloquear o console.

[English](guide.en.md) · [Voltar ao README](../README.md)

Os cinco minutos são para preparar o serviço. A primeira cópia pode levar mais
tempo, conforme a quantidade de saves e a velocidade da rede.

## 1. O que você precisa

- PS5 ligado, já desbloqueado, com **ftpsrv na porta 2121**.
- PC na mesma rede, com espaço livre para guardar os saves.
- No Windows, basta o executável. Para o outro caminho, instale Git, Docker e
  Docker Compose no computador.

Deixe o PC ligado enquanto quiser cópias automáticas. Escolha **Windows** ou
**Docker** abaixo. Os dois abrem a mesma interface no navegador.

## 2. Windows: baixar e abrir

1. Abra a [página de releases](https://github.com/bps2414/memcard/releases/latest).
   Baixe `memcard.exe` e `memcard.exe.sha256`. Guarde os dois numa pasta em que
   você possa gravar arquivos. Não precisa instalar Python.
2. Abra o PowerShell nessa pasta e confira o arquivo:

   ```powershell
   (Get-FileHash .\memcard.exe -Algorithm SHA256).Hash.ToLower()
   Get-Content .\memcard.exe.sha256
   ```

   O primeiro resultado deve ser igual ao hash no começo do segundo. Se não
   bater, baixe novamente antes de abrir.
3. Dê dois cliques em `memcard.exe`. Ele não tem assinatura digital. Se aparecer
   **O Windows protegeu o computador**, depois de conferir o hash use
   **Mais informações › Executar assim mesmo**.
4. Uma janela de console fica aberta e o navegador abre
   `http://127.0.0.1:8765`. Se o navegador não abrir, digite esse endereço.
   Na primeira vez, um assistente acha o PS5, faz a primeira cópia e configura
   os avisos; dá para pular e ajustar tudo depois em **Ajustes**.
5. Mantenha a janela de console aberta. Fechá-la encerra o serviço.
   Abrir o executável de novo, com ele já rodando, só reabre a interface.

<!-- PRINT: Windows, pasta com memcard.exe e arquivo SHA-256, sem dados pessoais -->
<!-- PRINT: interface atual na aba Cartões antes da primeira cópia -->

Os ajustes ficam em `config.toml`, criado ao salvar na interface. Os backups e
o registro ficam em `data/`. Tudo fica ao lado do executável. Preserve essa
pasta ao atualizar. No Windows, a atualização é manual; veja o
[README](../README.md#windows-sem-docker).

## 3. Docker: preparar e iniciar

Abra um terminal com Git, Docker e Docker Compose disponíveis. Execute os
quatro comandos do README:

```sh
git clone https://github.com/bps2414/memcard.git
cd memcard
cp config.example.toml config.toml
cp .env.example .env
```

Você deve ter `config.toml` e `.env` dentro da pasta `memcard`.
No PowerShell, `cp` também copia arquivos.

Abra `config.toml`. Na seção `[ps5]`, troque `host` pelo IP do seu PS5 e confira
`ftp_port = 2121`. Por exemplo, para um PS5 em `192.168.0.50`:

```toml
[ps5]
host = "192.168.0.50"
ftp_port = 2121
subnet = "192.168.0.0/24"
```

Edite essas linhas existentes; mantenha os outros ajustes. `subnet` indica a
rede em que procurar o console. Use a rede do **PS5**, não a rede interna do
Docker. No modo padrão do Compose, chamado *bridge*, o endereço visto pelo
contêiner pode ser de outra rede. Preencher `subnet` evita procurar nessa rede
interna. O exemplo cobre endereços `192.168.0.x`; adapte à sua rede.

Salve o arquivo e inicie:

```sh
docker compose up -d
```

Espere o Docker baixar a imagem e iniciar os serviços. Abra
`http://localhost:8765` nesse PC, ou `http://<ip-do-computador>:8765` em outro
dispositivo da mesma rede. Você deve ver a aba **Cartões**.
Se definiu `WEB_PASSWORD` no `.env`, entre com essa senha.

Os backups ficam em `data/`, dentro da pasta do projeto. O serviço continua
rodando ao fechar o terminal. O Compose inclui atualização automática da imagem;
os detalhes e a troca da pasta de backups estão no [README](../README.md#instalação).

<!-- PRINT: terminal com docker compose up -d concluído e serviços iniciados -->

## 4. Achar o PS5

Abra **Ajustes › Console**. Confira **Endereço do PS5** e **Porta do ftpsrv**.
Use **Procurar agora**. Quando achar, a tela confirma o IP e a porta e os campos
são atualizados. A busca usa o endereço e a rede digitados, mesmo antes de salvar.

A busca automática vem ligada. Se o endereço configurado não responder, ela
tenta encontrar o console e corrige o IP e a porta no `config.toml`.
Uma busca sem resultado é repetida a cada cinco minutos.

<!-- PRINT: Ajustes, seção Console e confirmação de PS5 encontrado com dados de exemplo -->

Se não encontrar:

1. Confira se o PS5 está ligado e o **ftpsrv continua carregado na porta 2121**.
   Tente **Procurar agora** novamente. Deve aparecer a confirmação do endereço.
2. Confira se PC e PS5 estão na mesma rede. Uma rede de convidados pode impedir
   que se comuniquem. Em **Rede a procurar (avançado)**, informe a rede do PS5,
   como `192.168.0.0/24`. No Docker bridge, confira também `subnet` no arquivo.
   Tente a busca de novo e clique em **Salvar ajustes** para guardar essa rede.
3. Confira se o firewall permite o Memcard acessar o PS5 na rede local.
   Se o PC usa VPN, confira se ela permite acesso à rede local. Corrija o
   bloqueio e tente novamente.
4. Se souber o IP, digite-o, confira a porta e clique em **Salvar ajustes**.
   A tela deve confirmar **Ajustes salvos**. Se continuar sem conexão, siga
   para o diagnóstico no passo 8.

Com o campo de rede vazio, a busca tenta a faixa do endereço configurado, a do PC e as
faixas comuns `192.168.1.x` e `192.168.0.x`. Uma rede preenchida limita a busca
àquela faixa. Reservar o IP do PS5 no roteador ajuda a mantê-lo igual.

## 5. Primeira cópia

Com o PS5 encontrado, volte a **Cartões**. A primeira cópia começa sozinha com
os ajustes padrão. Para iniciar manualmente, clique em **Copiar agora**.
Se já estiver copiando, aguarde essa rodada.

A tela mostra **Copiando os saves do PS5…** durante a cópia. Depois surgem os
cartões dos perfis e os blocos dos jogos. Clique num jogo, depois num save.
Você deve ver pelo menos uma versão guardada, com data e opção de baixar.

<!-- PRINT: Cartões após a primeira cópia e histórico de um save com versão guardada -->

Não há duração fixa. Muitos saves, Wi-Fi lento ou um jogo gravando podem
demorar mais. Há também uma espera inicial, por padrão de 20 segundos, quando
o console passa a responder. Deixe PC e PS5 ligados até terminar.

Abra **Registro** e confira o resumo `backup [...]`: ele informa novas versões,
arquivos inalterados, arquivos aguardando estabilizar e falhas. Para confirmar
a primeira cópia, confira as versões guardadas e **0 falhas**. Se houver saves
aguardando estabilizar, espere a próxima rodada e confira novamente.
Um console conectado, sozinho, ainda não confirma a cópia.

## 6. Avisos no Discord

Este passo é opcional. Use um servidor em que você possa criar webhooks.
O webhook é o endereço para o Memcard enviar mensagens ao canal.

1. No Discord, abra **Configurações do servidor › Integrações** e crie um
   webhook. Escolha o canal de texto e copie a URL. Você deve ver o webhook
   ligado ao canal escolhido. Veja também a
   [ajuda oficial do Discord](https://support.discord.com/hc/pt-br/articles/228383668-Usando-Webhooks).
2. No Memcard, abra **Ajustes › Avisos no Discord**. Cole a URL no campo
   **Webhook** e clique no **Salvar** ao lado dele. A tela confirma que foi salvo.
3. Clique em **Enviar teste**. No canal escolhido deve chegar **Teste do Memcard**.
   Se não chegar, confira a URL, o canal e a mensagem de erro na interface.

<!-- PRINT: Discord, webhook ligado ao canal escolhido, com URL escondida -->
<!-- PRINT: Ajustes, webhook configurado e mensagem de teste recebida no Discord -->

Não compartilhe essa URL. O Memcard a guarda em `data/secrets.json`.
Durante o uso, a mensagem da sessão é atualizada a cada cópia. Essas edições
não geram uma notificação por save. O idioma dos avisos fica em **Ajustes › Idioma**;
se mudar, clique em **Salvar ajustes**.

## 7. Como saber que está funcionando

Jogue e grave um save. Mantenha PS5 e PC ligados. Depois confira o histórico
desse save e **Registro**: uma mudança de conteúdo deve aparecer como uma versão
nova. Os arquivos iguais não são copiados outra vez.
Durante o jogo, versões próximas podem ser substituídas pela mais recente;
por padrão, fica uma a cada dez minutos.

Em **Registro › Integridade**, clique em **Conferir agora**. Espere a conclusão.
Com versões guardadas, o resultado deve informar versões íntegras e nenhum
problema. Isso confere os arquivos no PC, mesmo com o PS5 desligado.

<!-- PRINT: Registro com cópia concluída, zero falhas e conferência de integridade sem problemas -->

Ao desligar o PS5 ou entrar em repouso, o FTP deixa de responder. O Memcard
mostra o console fora de alcance e mantém as cópias já guardadas. Ele não
consegue ler um save depois que o console saiu da rede. Algo gravado depois
da última leitura fica para a próxima vez que o FTP responder.

No Discord, o resumo da sessão chega depois da tolerância a quedas de rede
(por padrão, três minutos após detectar a perda de conexão). Quando o PS5
voltar com o ftpsrv carregado, as cópias retomam sozinhas. O serviço no PC
precisa continuar rodando.

## 8. Se algo der errado

Confira o endereço em **Ajustes › Console**. Com o PS5 ligado e o ftpsrv
carregado, rode o diagnóstico. No Windows, abra o PowerShell na pasta do
executável:

```powershell
.\memcard.exe diag
```

No Docker, abra o terminal na pasta do projeto:

```sh
docker compose exec ps5-backup ps5backup diag
```

Você deve ver um bloco iniciado por **Diagnóstico de compatibilidade (somente
leitura)**. Ele testa as leituras no endereço já configurado, sem procurar
outro console nem mudar os ajustes. A última linha informa se as etapas
necessárias funcionaram ou o que faltou. Sem saves, não consegue testar a
leitura de um save. O texto da linha de comando fica em português.

<!-- PRINT: terminal com diagnóstico concluído usando PS5 de mentira, sem dados pessoais -->

Copie o bloco inteiro e abra uma
[issue de compatibilidade](https://github.com/bps2414/memcard/issues/new?template=compat.yml).
Informe o firmware do PS5, a versão do ftpsrv, o sistema do PC e se uma cópia
terminou. Diga o que você fez e o que apareceu. O diagnóstico omite IPs e
nomes/IDs de perfis e saves; não acrescente esses dados nem a URL do webhook.

Confira a [tabela de compatibilidade e a explicação do diagnóstico](COMPATIBILIDADE.md).
Um diagnóstico bem-sucedido confirma as leituras daquele momento. Confira
também as versões guardadas para confirmar o backup.

## 9. Restaurar um save

Abra o jogo e o save na interface. Escolha uma versão no histórico e baixe-a.
Você deve receber o arquivo no computador. O Memcard não o envia ao PS5.

Consulte o [roteiro de restauração manual](restaurar.md) antes de importar pelo
Garlic SaveMgr. Ele ainda reúne os casos a testar no console real; o guia final
depende desses resultados. Guarde o estado atual antes de qualquer tentativa.
A existência do backup não confirma que a restauração já foi testada.

<!-- PRINT: histórico de um save, versão escolhida e botão de baixar -->
