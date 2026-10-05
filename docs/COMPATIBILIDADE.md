# Compatibilidade

[English](COMPATIBILITY.en.md)

Só há uma combinação verificada em console real. Um diagnóstico bem-sucedido
mostra que as leituras necessárias responderam naquele momento; confirme também
que uma cópia termina e que as versões aparecem antes de relatar que funciona.

| Firmware | Servidor de FTP | Versão do servidor | Resultado | Observações | Quem relatou | Data |
|---|---|---|---|---|---|---|
| 13.42 | ftpsrv | 0.21.1 | Funciona | Combinação usada nos testes iniciais do projeto. | Relato inicial do projeto | Não registrada |

## Como relatar

Ligue o PS5, carregue o servidor FTP e confira o console configurado no Memcard.
O diagnóstico conecta somente ao endereço configurado; não procura outros
consoles, não altera o config e não grava nem apaga nada no PS5.

No Docker:

```sh
docker compose exec ps5-backup ps5backup diag
```

No Windows, dentro da pasta do executável:

```powershell
.\memcard.exe diag
```

Pelo código-fonte, com `PS5BACKUP_CONFIG` definido como no README:

```sh
python -c "import sys; sys.path.insert(0, 'app'); import ps5backup; sys.exit(ps5backup.main())" diag
```

Copie o bloco inteiro e abra uma [issue de compatibilidade](https://github.com/bps2414/memcard/issues/new?template=compat.yml).
Informe firmware, servidor e versão; diga se uma cópia real terminou e descreva
eventuais falhas. Não acrescente IP, nome/ID de perfil ou nome de save ao relato.

O relatório mostra versão do Memcard, sistema e Python, banner FTP, SYST e FEAT,
comportamento do MLSD, fatos `type`, `size` e `modify`, contagens de perfis,
metadados opcionais e tamanho/tempo do RETR do menor arquivo de save encontrado.
Banner e respostas são resumidos: códigos FTP, identificação `ftpsrv`/versão,
identificadores de sistema e capacidades conhecidas são preservados; texto livre
é omitido para impedir que respostas ou erros arbitrários exponham dados privados.
Nenhum nome, ID de perfil, IP ou nome de save é exibido. Title IDs podem ser
incluídos no relato se forem relevantes.

Código de saída **0**: conexão, login, navegação, MLSD com fatos válidos e leitura
de um save funcionaram. **1**: alguma etapa essencial falhou ou não pôde ser
verificada; a última linha diz o que faltou. Sem saves, o RETR não pode ser
verificado. Tamanho diferente também produz 1 (o save pode mudar durante o teste).
Ausência de `/user/appmeta` ou de um `savedata.db` legível não impede copiar saves
e é registrada como metadado opcional. Recusas de SYST/FEAT ficam registradas e
também não impedem a cópia. Não há alternativa com `LIST` para servidor sem MLSD.

`GET /api/diag` devolve `{"text": "..."}` e exige o mesmo login das outras rotas.
Usa `X-Lang` (`pt-BR`/`en`) quando informado, ou o idioma configurado em
`[notify] language`; a CLI sempre usa português. A interface ainda não tem botão.
