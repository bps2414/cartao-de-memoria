"""Textos dos avisos (Discord) e dos erros da API, em pt-BR e en.

A interface web tem o próprio dicionário em ui/index.html. O registro técnico
(backup.log) e a linha de comando ficam em português: o log é lido de volta pelo
painel e pela projeção, então o formato das linhas não pode variar com o idioma.
"""
LANGS = ("pt-BR", "en")
DEFAULT_LANG = "pt-BR"

TEXT = {
    "pt-BR": {
        # avisos da sessão
        "off_title": "🔴  PS5 desligado · sessão encerrada",
        "off_empty": "Nenhum save mudou nesta sessão.",
        "on_title": "🟢  PS5 ligado",
        "on_body": "Vigiando os saves. Nenhum mudou desde que o console ligou.",
        "saving_title": "💾  Guardando os saves desta sessão",
        "now_playing": "Agora: {games}",
        "now_idle": "Nenhum save mudou nos últimos {n} minutos.",
        "more_games": "… e mais {n} jogos",
        "f_duration": "Duração",
        "f_copies": "Cópias feitas",
        "f_saves": "Saves",
        "f_read": "Lido do PS5",
        "f_total": "Total guardado",
        "f_checked": "Última verificação",
        "f_on": "Ligado",
        "f_last_copy": "Última cópia",
        # outros avisos
        "copy_failed_title": "Falha ao copiar saves",
        "backup_failed_title": "Backup falhou",
        "new_profile_title": "👤  Perfil novo no PS5: {name}",
        "new_profile_in": "Os saves dele já entram no backup.",
        "new_profile_out": "Ele está fora do backup até você incluir na interface.",
        "space_title": "📦  Atenção ao espaço dos backups",
        "space_body": "Os backups ocupam {used} GB e restam {free} GB livres no disco. "
                      "Nada foi apagado. Veja Ajustes › Quanto guardar.",
        "weekly_title": "📅  Resumo da semana · {start} a {end}",
        "weekly_note": "Tempo estimado pelos momentos em que cada jogo gravou saves.",
        "f_played": "Tempo de jogo",
        "f_busiest": "Dia mais jogado",
        "week_delta": "{delta} MB na semana",
        "date_short": "{dd}/{mm}",
        "months": "jan fev mar abr mai jun jul ago set out nov dez",
        "verify_title": "⚠️  Conferência de integridade: {n} com problema",
        "verify_body": "Estas versões guardadas não batem mais com o checksum anotado na hora da cópia "
                       "(arquivo corrompido ou ausente). Nada foi apagado. Veja Registro › Integridade.",
        "verify_more": "… e mais {n}",
        "f_intact": "Versões íntegras",
        "test_title": "🎮  Teste do Cartão de Memória",
        "test_body": "Se você está lendo isto, os avisos estão chegando.",
        # erros da API
        "e_not_found": "não encontrado",
        "e_bad_path": "caminho inválido",
        "e_send_json": "envie JSON",
        "e_unknown_route": "rota desconhecida",
        "e_busy": "Já existe uma cópia em andamento.",
        "e_offline": "O PS5 não está respondendo. Ligue o console e carregue o ftpsrv.",
        "e_profile": "perfil ou modo inválido",
        "e_title": "jogo inválido",
        "e_url": "A URL precisa começar com https://",
        "e_no_webhook": "Nenhum webhook configurado.",
        "e_discord": "O Discord recusou o envio. Confira a URL do webhook.",
        "e_version": "versão inválida",
        "e_version_missing": "versão não encontrada",
        "e_auth": "Entre com a senha para continuar.",
        "e_login": "Senha incorreta.",
        "e_login_blocked": "Muitas tentativas erradas. Tente de novo em {minutes} minutos.",
        # erros de configuração
        "c_section": "[{section}] precisa ser uma seção",
        "c_unknown": "chave desconhecida em [{section}]: {keys}",
        "c_type": "[{section}] {key}: esperado {type}",
        "c_list": "[{section}] {key}: a lista só aceita textos",
        "c_min": "[{section}] {key}: mínimo {min}",
        "c_new_profiles": '[filter] new_profiles: use "include" ou "exclude"',
        "c_hhmm": "[triggers] schedule_daily_at: horário inválido {value} (use HH:MM)",
        "c_language": '[notify] language: use "pt-BR" ou "en"',
    },
    "en": {
        "off_title": "🔴  PS5 off · session ended",
        "off_empty": "No saves changed during this session.",
        "on_title": "🟢  PS5 on",
        "on_body": "Watching your saves. Nothing has changed since the console came on.",
        "saving_title": "💾  Backing up this session's saves",
        "now_playing": "Playing now: {games}",
        "now_idle": "No saves changed in the last {n} minutes.",
        "more_games": "… and {n} more games",
        "f_duration": "Duration",
        "f_copies": "Backups made",
        "f_saves": "Saves",
        "f_read": "Read from PS5",
        "f_total": "Total stored",
        "f_checked": "Last check",
        "f_on": "Powered on",
        "f_last_copy": "Last backup",
        "copy_failed_title": "Some saves could not be copied",
        "backup_failed_title": "Backup failed",
        "new_profile_title": "👤  New profile on the PS5: {name}",
        "new_profile_in": "Its saves are already being backed up.",
        "new_profile_out": "It stays out of the backup until you include it in the web interface.",
        "space_title": "📦  Backup storage needs attention",
        "space_body": "Backups take up {used} GB and the disk has {free} GB free. "
                      "Nothing was deleted. See Settings › How much to keep.",
        "weekly_title": "📅  Weekly summary · {start} – {end}",
        "weekly_note": "Play time is estimated from the moments each game wrote a save.",
        "f_played": "Play time",
        "f_busiest": "Busiest day",
        "week_delta": "{delta} MB this week",
        "date_short": "{mon} {day}",
        "months": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec",
        "verify_title": "⚠️  Integrity check: {n} with problems",
        "verify_body": "These stored versions no longer match the checksum recorded when they were copied "
                       "(corrupted or missing file). Nothing was deleted. See Log › Integrity.",
        "verify_more": "… and {n} more",
        "f_intact": "Intact versions",
        "test_title": "🎮  Cartão de Memória test",
        "test_body": "If you can read this, notifications are working.",
        "e_not_found": "not found",
        "e_bad_path": "invalid path",
        "e_send_json": "send JSON",
        "e_unknown_route": "unknown route",
        "e_busy": "A backup is already running.",
        "e_offline": "The PS5 is not responding. Turn the console on and load ftpsrv.",
        "e_profile": "invalid profile or mode",
        "e_title": "invalid game",
        "e_url": "The URL must start with https://",
        "e_no_webhook": "No webhook configured.",
        "e_discord": "Discord rejected the message. Check the webhook URL.",
        "e_version": "invalid version",
        "e_version_missing": "version not found",
        "e_auth": "Sign in to continue.",
        "e_login": "Wrong password.",
        "e_login_blocked": "Too many wrong attempts. Try again in {minutes} minutes.",
        "c_section": "[{section}] must be a section",
        "c_unknown": "unknown key in [{section}]: {keys}",
        "c_type": "[{section}] {key}: expected {type}",
        "c_list": "[{section}] {key}: the list only takes strings",
        "c_min": "[{section}] {key}: minimum is {min}",
        "c_new_profiles": '[filter] new_profiles: use "include" or "exclude"',
        "c_hhmm": "[triggers] schedule_daily_at: invalid time {value} (use HH:MM)",
        "c_language": '[notify] language: use "pt-BR" or "en"',
    },
}


def tr(lang, name, /, **kw):
    table = TEXT.get(lang) or TEXT[DEFAULT_LANG]
    return (table.get(name) or TEXT[DEFAULT_LANG][name]).format(**kw)


class Msg(ValueError):
    """Erro com texto traduzível. str() devolve em português (log e CLI)."""

    def __init__(self, name, /, **kw):
        self.name, self.kw = name, kw
        super().__init__(tr(DEFAULT_LANG, name, **kw))

    def text(self, lang):
        return tr(lang, self.name, **self.kw)
