"""
🎪 PINKIE PIE — Bot da CRM
══════════════════════════════════════════════════════════════════
Bot de Discord (discord.py) com a personalidade da Pinkie Pie:
alegre, travessa e engraçadinha — a palhaça oficial do servidor CRM.

As interações do dia a dia (piada, abraço, festa, sorte, conselho,
oi, pix/dinheiro) não usam mais comando com prefixo: basta chamar a
Pinkie pelo nome (ou marcar @Pinkie Pie) numa frase normal, tipo:

    "conte uma piada, pink"
    "pinkie me dá um abraço"
    "bora decretar festa pinkie!"
    "pinkie, qual minha sorte hoje?"
    "pinkie me dá um conselho"
    "pinkie me manda um pix"

Ela procura essas palavras-chave na mensagem (com tolerância a erro
de digitação e falta de acento) e responde na hora. Se chamar ela e
não pedir nada específico, ela só se apresenta.

O único comando com prefixo que sobrou é o `pk!configurarcarta`,
porque é uma ação técnica de staff (republicar o painel), não uma
interação de personalidade.

Já vem com o sistema de "Carta Surpresa da Pinkie" integrado: um
formulário onde qualquer um pode escrever uma cartinha (com nome ou
anônima), que cai num canal de revisão pra staff aprovar ou recusar
antes de ir pro mundo — a votação é feita REAGINDO com ✅ ou ❌ na
mensagem, sem botão nenhum.

E também o sistema de ANIVERSÁRIOS: no canal CANAL_ANIVERSARIO_ID,
basta a pessoa mandar a data (ex.: "13/05") que a Pinkie registra.
Se ela já tinha um aniversário salvo e mandar outra data, a Pinkie
pergunta com botões (Sim, alterar / Não, manter). No dia certo, ela
manda os parabéns no mesmo canal. Fora desse canal, datas são ignoradas.

COMO USAR
──────────
1. pip install -U discord.py python-dotenv
2. Crie um arquivo .env do lado desse bot.py com:
       DISCORD_TOKEN=seu_token_aqui
3. Preencha os IDs marcados com "TROQUE AQUI" logo abaixo
   (cargos de staff e canais do painel/revisão da carta).
4. No painel do Discord Developer, ative os intents:
   SERVER MEMBERS INTENT e MESSAGE CONTENT INTENT.
5. python bot.py
══════════════════════════════════════════════════════════════════
"""

import difflib
import json
import os
import random
import re
import time
import unicodedata
import uuid
from datetime import date, datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    ZoneInfo = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ══════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO GERAL — TROQUE AQUI pelos dados reais do servidor CRM
# ══════════════════════════════════════════════════════════════════

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIXO = "pk!"  # usado só pelo pk!configurarcarta (comando técnico de staff)

# Rosa-choque bem "Pinkie" pros embeds
COR_PINKIE = discord.Colour.from_rgb(255, 105, 180)

# Cargos que contam como staff (administrator sempre conta também)
CARGOS_STAFF_IDS = [
    111111111111111111,  # TROQUE AQUI — cargo de staff nº1 da CRM
    222222222222222222,  # TROQUE AQUI — cargo de staff nº2 da CRM (se tiver)
]

# Canais do sistema de Carta Surpresa
CANAL_PAINEL_CARTA_ID = 1549826297834766447        # canal dos membros — onde fica o painel fixo
CANAL_REVISAO_CARTA_ID = 1549826189802348694       # canal da staff — onde a staff avalia as cartas
CANAL_PUBLICACAO_CARTA_ID = 1538287965116039211    # canal público — onde a carta é postada quando aceita

# Canal do sistema de Aniversários — é o ÚNICO canal onde dá pra registrar/alterar
# o aniversário, e também onde a Pinkie manda os parabéns no dia certo.
CANAL_ANIVERSARIO_ID = 1563265822120484934

# Imagem que acompanha o painel da Carta Surpresa (mostrada no embed pros membros)
IMAGEM_PAINEL_CARTA_URL = (
    "https://cdn.discordapp.com/attachments/926913851172204577/"
    "1549833284694057100/ChatGPT_Image_16_de_set._de_2026_14_23_54.png"
    "?ex=6aac2239&is=6aaad0b9&hm=78c833317111168a47e64177c61d1d09be2544112f05e5e293b6d8f20419d031"
)

# Emojis usados pra votar nas cartas (reação, não botão)
EMOJI_ACEITAR = "✅"
EMOJI_RECUSAR = "❌"

_CARTA_DATA_PATH = os.getenv("PINKIE_CARTA_DATA_PATH", "/data/pinkie_carta.json")
_ANIVERSARIO_DATA_PATH = os.getenv("PINKIE_ANIVERSARIO_DATA_PATH", "/data/pinkie_aniversarios.json")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
# intents.reactions já vem True no default(); precisamos dele pra escutar as
# reações de ✅/❌ que a staff coloca na carta.

bot = commands.Bot(command_prefix=PREFIXO, intents=intents, help_command=None)


# ══════════════════════════════════════════════════════════════════
# TEMPERO DA PINKIE — fraseado solto pra dar vida ao bot
# ══════════════════════════════════════════════════════════════════

FRASES_ONLINE = [
    "🎪 chegueeei! alguém pediu confete?",
    "🤡 tá pronto o picadeiro, bora bagunçar (o bem-humorado tipo de bagunça)!",
    "🎈 *POFT* apareci do nada, como sempre. oi genteee!",
]

FRASES_PIADA = [
    "por que o esqueleto não brigou com ninguém? porque ele não tinha estômago pra isso. 💀🤣",
    "sabe qual é o cúmulo do exagero? um palhaço com medo de plateia. É... eu mesma às vezes. 🤡",
    "por que a Pinkie trouxe uma escada pro Discord? porque falaram que os níveis de hype tavam baixos! 🪜🎉",
    "não confia em átomo. eles inventam TUDO. 🧪✨",
]

FRASES_ABRACO = [
    "🤗 *abraço apertado de palhaço* — cuidado que eu meio que aperto forte quando gosto de alguém!",
    "🎈 vem cá, {alvo}! um abraço de confete e purpurina, cortesia da casa.",
    "🤡💞 abraço enviado! (com direito a nariz vermelho, é tradição)",
]

FRASES_FESTA = [
    "🎉🎊 CONFETE PRA TODO MUNDO! alguém disse festa?? 🥳",
    "🎪🎈 bora montar o picadeiro aqui mesmo, ninguém segura essa energia!",
    "🎵 *música de circo tocando ao fundo* — tá OFICIALMENTE decretada: hoje é dia de festa!",
]

FRASES_SORTE = [
    "🍀 hoje é dia de sorte! (ou pelo menos eu acho, minha bola de cristal é uma rosquinha)",
    "🔮 a Pinkie prevê: muitas risadas no seu futuro próximo!",
    "✨ sua sorte de hoje: alguém vai rir de uma piada sua. talvez seja de pena, mas vale!",
]

FRASES_CONSELHO = [
    "💡 conselho da Pinkie: se a vida te der limão, faz uma festa de limonada. literalmente. eu já fiz.",
    "💡 conselho da Pinkie: ri primeiro, pensa depois. funciona quase sempre!",
    "💡 conselho da Pinkie: um pouco de confete resolve muita coisa (não emocionalmente, mas visualmente sim).",
]

FRASES_PIX = [
    "💸 Pix? minha carteira é feita de confete, infelizmente não é aceita em lugar nenhum. mas aceito um abraço como pagamento!",
    "🤡 ahh eu ADORARIA, mas todo meu dinheiro eu já gastei em purpurina e balão. bota na conta da festa!",
    "🎪 sem Pix aqui, só tenho piada, abraço e muito confete pra doar. topa essa moeda?",
]

# Apresentação varia pra não parecer sempre a mesma resposta robotizada.
FRASES_APRESENTACAO = [
    (
        "🎪 Oiii, {alvo}! Eu sou a **Pinkie Pie**, a palhacinha oficial da CRM! 🤡🎈\n"
        "Adoro espalhar piada, confete e uma bagunça (do tipo boa) por aqui.\n\n"
        "É só falar comigo numa frase normal! Me chama pelo nome e pede uma piada, um "
        "abraço, uma festa, sua sorte do dia ou um conselho que eu já te respondo. 💌"
    ),
    (
        "🤡 Opa, {alvo}! Chamou e eu apareci, como sempre — efeito colateral de ser a "
        "palhacinha oficial daqui.\n\n"
        "Não entendi exatamente o que você quer, mas pode falar numa frase solta: peça "
        "uma piada, um abraço, festa, sua sorte de hoje ou um conselho! 🎈"
    ),
    (
        "🎈 *POFT* apareci! Sou a **Pinkie Pie**, e ainda não peguei o que você pediu "
        "nessa mensagem, {alvo}.\n\n"
        "Tenta assim: me chama e pede piada, abraço, festa, sorte ou conselho — numa "
        "frase de boa, sem comando nenhum! 🤡✨"
    ),
]


def frase_aleatoria(lista: list) -> str:
    return random.choice(lista)


# Regex pra pegar "pinkie", "pinkie pie" ou só "pink" em qualquer canto da
# frase, com ou sem maiúscula (cobre gente que chama ela de "pink" mesmo).
_NOME_PINKIE_REGEX = re.compile(r"\bpink(ie)?( pie)?\b", re.IGNORECASE)

# Gatilhos de linguagem natural — cada um cobre a intenção principal e
# algumas variações comuns de como alguém pediria isso numa frase solta.
# São a primeira tentativa (rápida e exata); se nenhum bater, ainda existe
# uma segunda passada tolerante a erro de digitação (_categoria_por_fuzzy).
_GATILHO_PIADA = re.compile(r"piada|\bmeu?\s+fa[cç]a?\s+rir\b|\brir\b", re.IGNORECASE)
_GATILHO_ABRACO = re.compile(r"abra[cç]o", re.IGNORECASE)
_GATILHO_FESTA = re.compile(r"\bfesta\b|comemora[cç][aã]o|\bcomemorar\b", re.IGNORECASE)
_GATILHO_SORTE = re.compile(r"\bsorte\b|previs[aã]o|\bfuturo\b|hor[oó]scopo", re.IGNORECASE)
_GATILHO_CONSELHO = re.compile(
    r"conselho|concelho|me\s+aconselh|aconselhar|\bdica\b", re.IGNORECASE
)
_GATILHO_OI = re.compile(r"\boi+\b|\bol[aá]\b|\bsalve\b|\be\s*a[ií]\b|\bopa\b", re.IGNORECASE)
_GATILHO_PIX = re.compile(
    r"\bpix\b|dinheiro|\bgrana\b|doa[cç][aã]o|empr[eé]sta|empr[eé]stimo|\bmoney\b",
    re.IGNORECASE,
)

# ── Tolerância a erro de digitação ──────────────────────────────────
# As regex acima cobrem os jeitos mais comuns de pedir cada coisa, mas
# sempre aparece alguém que escreve errado de um jeito que a gente nem
# previu (ex.: "consêlho", "consei", "abrasso"). Em vez de ficar caçando
# variação por variação, essa segunda passada compara CADA PALAVRA da
# mensagem (sem acento, minúscula) contra uma palavra "âncora" de cada
# categoria usando distância de edição (difflib). Se a palavra da
# mensagem for bem parecida com a âncora, a categoria conta como
# reconhecida — sem precisar bater 100% com a grafia certa.
_ANCORAS_POR_CATEGORIA = {
    "piada": "piada",
    "abraco": "abraco",
    "festa": "festa",
    "sorte": "sorte",
    "conselho": "conselho",
    "oi": "oi",
    "pix": "pix",
}


def _normalizar(texto: str) -> str:
    """minúsculo e sem acento/cedilha, pra comparação tolerante a erro de
    digitação (ex.: 'concelho' e 'conselho' ficam bem parecidos)."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def _categoria_por_fuzzy(conteudo: str):
    """Segunda tentativa, só usada se nenhuma regex exata bateu: quebra a
    mensagem em palavras e vê se alguma é bem parecida (~75%) com a âncora
    de alguma categoria. Pega erro de digitação tipo 'consei', 'abrasso',
    'sorti' etc. sem precisar listar cada variação manualmente."""
    palavras = re.findall(r"[a-zà-ú]+", _normalizar(conteudo))
    for palavra in palavras:
        if len(palavra) < 3:
            continue  # palavra curta demais gera falso positivo fácil
        for categoria, ancora in _ANCORAS_POR_CATEGORIA.items():
            parecido = difflib.SequenceMatcher(None, palavra, ancora).ratio()
            if parecido >= 0.75:
                return categoria
    return None


def _apresentacao_pinkie(autor_mention: str) -> str:
    return frase_aleatoria(FRASES_APRESENTACAO).format(alvo=autor_mention)


def _resposta_interacao_natural(message: discord.Message, conteudo: str):
    """Olha o conteúdo da mensagem (que já chamou a Pinkie pelo nome ou
    marcou ela) e devolve a resposta certa pra intenção detectada, ou None
    se não reconheceu nenhum pedido — aí ela só se apresenta.

    Primeiro tenta bater nas regex exatas (mais precisas). Se nenhuma bater,
    faz uma segunda tentativa tolerante a erro de digitação antes de desistir
    e cair na apresentação."""

    if _GATILHO_PIADA.search(conteudo):
        return f"🤡 {frase_aleatoria(FRASES_PIADA)}"

    if _GATILHO_ABRACO.search(conteudo):
        return _resposta_abraco(message)

    if _GATILHO_FESTA.search(conteudo):
        return frase_aleatoria(FRASES_FESTA)

    if _GATILHO_SORTE.search(conteudo):
        return frase_aleatoria(FRASES_SORTE)

    if _GATILHO_CONSELHO.search(conteudo):
        return frase_aleatoria(FRASES_CONSELHO)

    if _GATILHO_PIX.search(conteudo):
        return frase_aleatoria(FRASES_PIX)

    if _GATILHO_OI.search(conteudo):
        return (
            f"OIOIOI {message.author.mention}! 🎉 bem-vindo(a) ao meu picadeiro "
            f"particular!"
        )

    # Nenhuma regex exata bateu — última chance, tolerante a erro de
    # digitação, antes de cair na apresentação genérica.
    categoria = _categoria_por_fuzzy(conteudo)
    if categoria == "piada":
        return f"🤡 {frase_aleatoria(FRASES_PIADA)}"
    if categoria == "abraco":
        return _resposta_abraco(message)
    if categoria == "festa":
        return frase_aleatoria(FRASES_FESTA)
    if categoria == "sorte":
        return frase_aleatoria(FRASES_SORTE)
    if categoria == "conselho":
        return frase_aleatoria(FRASES_CONSELHO)
    if categoria == "pix":
        return frase_aleatoria(FRASES_PIX)
    if categoria == "oi":
        return (
            f"OIOIOI {message.author.mention}! 🎉 bem-vindo(a) ao meu picadeiro "
            f"particular!"
        )

    return None


def _resposta_abraco(message: discord.Message) -> str:
    alvo_membros = [
        m for m in message.mentions if bot.user is None or m.id != bot.user.id
    ]
    alvo = alvo_membros[0].mention if alvo_membros else message.author.mention
    return frase_aleatoria(FRASES_ABRACO).format(alvo=alvo)


# ══════════════════════════════════════════════════════════════════
# FUNÇÕES BASE — usadas pelo resto do bot (e pelo módulo de carta)
# ══════════════════════════════════════════════════════════════════

async def _garantir_canal(canal_id: int):
    """Busca um canal pelo ID: primeiro no cache, depois na API."""
    if not canal_id:
        return None
    canal = bot.get_channel(canal_id)
    if canal is not None:
        return canal
    try:
        return await bot.fetch_channel(canal_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None


def _e_staff(membro: discord.Member) -> bool:
    """Confere se o membro é staff (administrador ou tem um dos cargos configurados)."""
    if not isinstance(membro, discord.Member):
        return False
    if membro.guild_permissions.administrator:
        return True
    cargos_do_membro = {cargo.id for cargo in membro.roles}
    return any(cid in cargos_do_membro for cid in CARGOS_STAFF_IDS)


async def _achar_painel_existente(canal, titulo_esperado: str):
    """Vasculha as últimas mensagens do canal atrás de um painel que a própria
    Pinkie já tenha mandado (mesmo título, mandado por ela, sem os campos que
    só as cartas individuais têm). É o plano B pra quando o ID salvo em disco
    não existe mais (ex.: JSON não persistiu entre deploys) — evita mandar um
    painel duplicado do zero."""
    try:
        async for mensagem in canal.history(limit=50):
            if bot.user is None or mensagem.author.id != bot.user.id:
                continue
            if not mensagem.embeds:
                continue
            embed_existente = mensagem.embeds[0]
            if embed_existente.title != titulo_esperado:
                continue
            if embed_existente.fields:
                continue  # painel não tem campos; carta individual tem
            return mensagem
    except (discord.Forbidden, discord.HTTPException):
        pass
    return None


async def _publicar_ou_reaproveitar_painel(
    canal, dados: dict, chave_id: str, embed: discord.Embed, view: discord.ui.View
):
    """Edita a mensagem do painel se ela ainda existir. Se o ID salvo não
    funcionar (ou nem existir), procura no histórico do canal antes de mandar
    uma mensagem nova — assim, mesmo se _CARTA_DATA_PATH não tiver persistido
    entre deploys, o painel não duplica."""
    mensagem_id = dados.get(chave_id)
    if mensagem_id:
        try:
            mensagem = await canal.fetch_message(mensagem_id)
            await mensagem.edit(embed=embed, view=view)
            return mensagem
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    existente = await _achar_painel_existente(canal, embed.title)
    if existente is not None:
        try:
            await existente.edit(embed=embed, view=view)
            print(f"[pinkie-carta] achei um painel existente no histórico (msg {existente.id}) e reaproveitei em vez de duplicar.")
            return existente
        except (discord.Forbidden, discord.HTTPException):
            pass

    return await canal.send(embed=embed, view=view)


# ══════════════════════════════════════════════════════════════════
# EVENTOS BÁSICOS
# ══════════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"{frase_aleatoria(FRASES_ONLINE)}  (logada como {bot.user})")

    try:
        bot.add_view(PainelCarta())
        status = await _configurar_painel_carta()
        print(f"[pinkie-carta] {status}")
    except Exception as e:
        print(f"[pinkie-carta] erro ao configurar o painel da carta surpresa: {e!r}")

    # on_ready pode rodar mais de uma vez (reconexões) — só prepara os
    # aniversários e inicia os loops se eles ainda não estiverem rodando.
    if not _checar_aniversarios.is_running():
        _verificar_armazenamento_aniversario()
        try:
            # Antes de qualquer parabéns, lê o canal INTEIRO e reconstrói o que
            # estiver faltando no /data (ex.: volume novo, JSON perdido).
            await _sincronizar_aniversarios_do_historico()
        except Exception as e:
            print(f"[pinkie-aniversario] erro ao ler o histórico do canal: {e!r}")
        _checar_aniversarios.start()
        _ressincronizar_aniversarios.start()


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    conteudo = message.content or ""

    # Canal de aniversários: se a mensagem for uma data (ex.: "13/05"), a
    # Pinkie registra/atualiza o aniversário e pronto. Só funciona NESSE
    # canal — a mesma mensagem em qualquer outro canal é ignorada aqui.
    if message.channel.id == CANAL_ANIVERSARIO_ID and _ANIVERSARIO_REGEX.match(conteudo):
        await _tratar_mensagem_aniversario(message, conteudo)
        return

    # Se marcou a Pinkie com uma @menção DE VERDADE (escolhida no autocomplete
    # do Discord, o que deixa a tag "<@ID>" escrita no texto) ou falou o nome
    # dela (ou "pink") na mensagem, ela olha se tem algum pedido reconhecível
    # na frase (piada, abraço, festa, sorte, conselho, pix, oi) e responde na
    # hora. Se não reconhecer nada (nem com a tolerância a erro de digitação),
    # ela só se apresenta.
    #
    # IMPORTANTE: não usamos `bot.user in message.mentions` aqui de propósito.
    # Quando alguém RESPONDE (reply) a uma mensagem da Pinkie, o Discord
    # adiciona ela em message.mentions automaticamente (é o "ping de
    # resposta"), mesmo que a pessoa não tenha digitado nada com o nome dela
    # — foi assim que "tetando" e outras respostas neutras dispararam a
    # apresentação de novo. Checando o texto direto (a tag "<@ID>" só aparece
    # no conteúdo quando é uma @menção explícita) a gente ignora esse ping
    # "de brinde" da resposta e só reage quando a pessoa chamou ela mesmo.
    mencionou_de_verdade = bool(
        bot.user and re.search(rf"<@!?{bot.user.id}>", conteudo)
    )
    foi_chamada = mencionou_de_verdade or _NOME_PINKIE_REGEX.search(conteudo)
    if foi_chamada:
        resposta = _resposta_interacao_natural(message, conteudo)
        if resposta:
            await message.reply(resposta)
        else:
            await message.reply(_apresentacao_pinkie(message.author.mention))

    await bot.process_commands(message)


@bot.command(name="configurarcarta")
async def cmd_configurar_carta(ctx: commands.Context):
    """Comando manual (só staff) pra forçar a publicação/atualização do painel
    da Carta Surpresa sem precisar reiniciar o bot — ótimo pra debugar se ele
    não apareceu sozinho no on_ready (canal errado, sem permissão, etc)."""
    if not isinstance(ctx.author, discord.Member) or not _e_staff(ctx.author):
        await ctx.reply("Só a staff pode usar esse comando! 🎪")
        return
    status = await _configurar_painel_carta()
    await ctx.reply(f"🎪 {status}")


# ══════════════════════════════════════════════════════════════════
# ANIVERSÁRIOS DA PINKIE — registro por mensagem + parabéns no dia
#
# Funciona SÓ em CANAL_ANIVERSARIO_ID. A pessoa manda a data (dd/mm,
# aceita também dd-mm, dd.mm e, se quiser, com ano no fim — o ano é
# ignorado e nunca é salvo). A Pinkie responde:
#
#   • sem aniversário salvo  → registra e confirma.
#   • já tinha o MESMO dia   → avisa que já estava anotado.
#   • já tinha OUTRO dia     → pergunta com botões "Sim, alterar" /
#                              "Não, manter" (só quem escreveu clica).
#
# Um loop checa de 10 em 10 minutos (fuso de São Paulo) se tem alguém
# fazendo aniversário e manda os parabéns no mesmo canal, uma vez só
# por ano. Quem nasceu em 29/02 é parabenizado em 28/02 nos anos não
# bissextos.
#
# Tudo é salvo em /data/pinkie_aniversarios.json e, além disso, a Pinkie
# relê o canal inteiro ao ligar (e de 6 em 6 horas) pra recuperar qualquer
# aniversário que estiver faltando — o canal é o backup. O bot precisa da
# permissão "Ler Histórico de Mensagens" nesse canal.
# ══════════════════════════════════════════════════════════════════

# Fuso usado pra decidir "que dia é hoje" (tem fallback fixo UTC-3 caso o
# sistema não tenha o banco de fusos instalado — o Brasil não usa mais
# horário de verão, então UTC-3 fixo é seguro).
try:
    _FUSO_ANIVERSARIO = ZoneInfo("America/Sao_Paulo") if ZoneInfo else timezone(timedelta(hours=-3))
except Exception:
    _FUSO_ANIVERSARIO = timezone(timedelta(hours=-3))

# Mensagem inteira tem que ser só uma data: "13/05", "13-5", "13.05", "13/05/2000".
_ANIVERSARIO_REGEX = re.compile(
    r"^\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})(?:\s*[/\-.]\s*\d{2,4})?\s*$"
)

FRASES_PARABENS = [
    "🎉 PARABÉÉÉNS, {alvo}!! hoje o picadeiro inteiro é seu! 🥳🎈",
    "🎂 {alvo}, hoje é SEU dia!! confete, balão e bolo (imaginário) por minha conta! 🎊",
    "🤡🎈 *POFT* apareci só pra te dar os parabéns, {alvo}!! que seu dia seja uma festa!",
]


def _carregar_dados_aniversario() -> dict:
    try:
        with open(_ANIVERSARIO_DATA_PATH, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except FileNotFoundError:
        print(
            f"[pinkie-aniversario] {_ANIVERSARIO_DATA_PATH} não existe ainda (primeira vez, "
            f"ou o volume persistente não tá montado nesse caminho) — começando do zero."
        )
        dados = {}
    except json.JSONDecodeError as e:
        print(f"[pinkie-aniversario] {_ANIVERSARIO_DATA_PATH} tá corrompido ({e!r}) — começando do zero.")
        dados = {}
    dados.setdefault("aniversarios", {})  # {"<user_id>": {"dia": 13, "mes": 5}}
    dados.setdefault("parabens", {})      # {"<user_id>": "<ano em que já foi parabenizado>"}
    return dados


def _salvar_dados_aniversario(dados: dict) -> None:
    """Grava em /data (ou no caminho de PINKIE_ANIVERSARIO_DATA_PATH). Escreve
    num arquivo temporário e troca no final, assim um crash no meio da
    gravação nunca deixa o JSON pela metade."""
    try:
        pasta = os.path.dirname(_ANIVERSARIO_DATA_PATH)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        tmp = _ANIVERSARIO_DATA_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, _ANIVERSARIO_DATA_PATH)
    except OSError as e:
        print(
            f"[pinkie-aniversario] ⚠️ NÃO CONSEGUI SALVAR {_ANIVERSARIO_DATA_PATH}: {e!r} — "
            f"confere se existe um Volume montado nesse caminho, senão os aniversários "
            f"somem a cada deploy."
        )


def _formatar_data(dia: int, mes: int) -> str:
    return f"{dia:02d}/{mes:02d}"


def _parse_aniversario(conteudo: str):
    """Devolve (dia, mes) se for uma data válida, ou None. Usa 2000 (ano
    bissexto) só pra validar, assim 29/02 é aceito."""
    m = _ANIVERSARIO_REGEX.match(conteudo)
    if not m:
        return None
    dia, mes = int(m.group(1)), int(m.group(2))
    try:
        date(2000, mes, dia)
    except ValueError:
        return None
    return dia, mes


def _embed_aniversario(titulo: str, descricao: str) -> discord.Embed:
    embed = discord.Embed(title=titulo, description=descricao, color=COR_PINKIE)
    embed.set_footer(text="🎪 Pinkie Pie  •  aniversários")
    embed.timestamp = discord.utils.utcnow()
    return embed


class _ViewConfirmarAlteracao(discord.ui.View):
    """Botões "Sim, alterar" / "Não, manter" que aparecem quando alguém que
    já tem aniversário registrado manda uma data diferente. Só quem escreveu
    a data consegue clicar. Depois de clicar (ou do tempo acabar), os botões
    ficam desativados."""

    def __init__(self, autor_id: int, dia: int, mes: int):
        super().__init__(timeout=120)
        self.autor_id = autor_id
        self.dia = dia
        self.mes = mes
        self.message = None  # preenchido depois de enviar, usado no timeout

    def _desativar(self):
        for item in self.children:
            item.disabled = True

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor_id:
            await interaction.response.send_message(
                "Esses botões são da pessoa que mandou a data! 🎈", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Sim, alterar", emoji="✅", style=discord.ButtonStyle.success)
    async def sim(self, interaction: discord.Interaction, button: discord.ui.Button):
        dados = _carregar_dados_aniversario()
        dados["aniversarios"][str(self.autor_id)] = {"dia": self.dia, "mes": self.mes}
        # Se mudou a data, libera os parabéns de novo (vale pro ano atual).
        dados["parabens"].pop(str(self.autor_id), None)
        _salvar_dados_aniversario(dados)

        self._desativar()
        embed = _embed_aniversario(
            "🎂 Aniversário Atualizado!!",
            f"prontinho, <@{self.autor_id}>!! seu novo aniversário é "
            f"**{_formatar_data(self.dia, self.mes)}** 🥳🎈",
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    @discord.ui.button(label="Não, manter", emoji="🚫", style=discord.ButtonStyle.danger)
    async def nao(self, interaction: discord.Interaction, button: discord.ui.Button):
        dados = _carregar_dados_aniversario()
        atual = dados["aniversarios"].get(str(self.autor_id))
        texto_atual = _formatar_data(atual["dia"], atual["mes"]) if atual else "o que já estava"

        self._desativar()
        embed = _embed_aniversario(
            "🎂 Tudo certo, mantive!",
            f"ok!! continua valendo **{texto_atual}** 🎈",
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        self._desativar()
        if self.message is not None:
            try:
                embed = _embed_aniversario(
                    "🎂 Ficou sem resposta…",
                    "ninguém clicou, então mantive seu aniversário como estava! 🎈\n"
                    "se ainda quiser mudar, é só mandar a data de novo.",
                )
                await self.message.edit(embed=embed, view=self)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass


async def _tratar_mensagem_aniversario(message: discord.Message, conteudo: str) -> None:
    """Roda quando alguém manda algo com cara de data no canal de aniversário."""
    data = _parse_aniversario(conteudo)
    if data is None:
        await message.reply(
            "Hmm, essa data não existe no meu calendário de palhaça! 🤡\n"
            "manda assim: **dia/mês** (ex.: `13/05`).",
            mention_author=False,
        )
        return

    dia, mes = data
    dados = _carregar_dados_aniversario()
    existente = dados["aniversarios"].get(str(message.author.id))

    # 1) Primeira vez: registra direto.
    if existente is None:
        dados["aniversarios"][str(message.author.id)] = {"dia": dia, "mes": mes}
        _salvar_dados_aniversario(dados)
        embed = _embed_aniversario(
            "🎂 Aniversário Registrado!!",
            f"anotei aqui, {message.author.mention}!! 🤡🎈\n\n"
            f"📅 Seu aniversário: **{_formatar_data(dia, mes)}**\n"
            f"no dia certo eu venho aqui dar parabéns pra você!! 🥳🎊",
        )
        await message.reply(embed=embed)
        return

    # 2) Mesmo dia que já estava salvo: não precisa perguntar nada.
    if existente["dia"] == dia and existente["mes"] == mes:
        embed = _embed_aniversario(
            "🎂 Já tava anotado!",
            f"seu aniversário já é **{_formatar_data(dia, mes)}** mesmo, {message.author.mention}! 🎈",
        )
        await message.reply(embed=embed, mention_author=False)
        return

    # 3) Data diferente: pergunta antes de trocar.
    embed = _embed_aniversario(
        "🎂 Quer mudar seu aniversário?",
        f"{message.author.mention}, eu já tenho **{_formatar_data(existente['dia'], existente['mes'])}** "
        f"anotado pra você.\n"
        f"quer trocar pra **{_formatar_data(dia, mes)}**? 🤔🎈",
    )
    view = _ViewConfirmarAlteracao(message.author.id, dia, mes)
    view.message = await message.reply(embed=embed, view=view)


def _aniversariantes_de_hoje(dados: dict, hoje: date) -> list:
    """IDs (str) de quem faz aniversário hoje e ainda não foi parabenizado
    neste ano. Em ano não bissexto, quem é de 29/02 é parabenizado em 28/02."""
    ano = str(hoje.year)
    bissexto = (hoje.year % 4 == 0 and hoje.year % 100 != 0) or hoje.year % 400 == 0
    resultado = []
    for user_id, reg in dados["aniversarios"].items():
        if dados["parabens"].get(user_id) == ano:
            continue
        bate = (reg["dia"], reg["mes"]) == (hoje.day, hoje.month)
        if not bate and not bissexto and (reg["dia"], reg["mes"]) == (29, 2) and (hoje.day, hoje.month) == (28, 2):
            bate = True
        if bate:
            resultado.append(user_id)
    return resultado


@tasks.loop(minutes=10)
async def _checar_aniversarios():
    """De 10 em 10 minutos vê quem faz aniversário hoje (no fuso de São Paulo)
    e manda os parabéns no canal de aniversários, uma vez só por ano."""
    try:
        hoje = datetime.now(_FUSO_ANIVERSARIO).date()
        dados = _carregar_dados_aniversario()
        pendentes = _aniversariantes_de_hoje(dados, hoje)
        if not pendentes:
            return

        canal = await _garantir_canal(CANAL_ANIVERSARIO_ID)
        if canal is None:
            print(f"[pinkie-aniversario] não encontrei o canal {CANAL_ANIVERSARIO_ID} pra mandar os parabéns.")
            return

        for user_id in pendentes:
            membro = canal.guild.get_member(int(user_id)) if getattr(canal, "guild", None) else None
            if membro is None:
                continue  # saiu do servidor — não parabeniza (nem marca, caso volte no mesmo dia)

            embed = _embed_aniversario(
                "🎂 Feliz Aniversário!!",
                frase_aleatoria(FRASES_PARABENS).format(alvo=membro.mention),
            )
            try:
                await canal.send(content=membro.mention, embed=embed)
            except (discord.Forbidden, discord.HTTPException) as e:
                print(f"[pinkie-aniversario] não consegui mandar os parabéns pra {user_id}: {e!r}")
                continue

            dados["parabens"][user_id] = str(hoje.year)
            _salvar_dados_aniversario(dados)
    except Exception as e:
        print(f"[pinkie-aniversario] erro no loop de parabéns: {e!r}")


# ── Memória infinita: o canal inteiro é o "backup" dos aniversários ──────
# O /data é a fonte principal, mas o próprio canal também guarda tudo: cada
# "Aniversário Registrado!!" / "Aniversário Atualizado!!" (da Pinkie ou de
# outro bot com o mesmo formato, tipo a Lilu), cada "Feliz Aniversário!!" e
# cada data mandada por alguém. Na inicialização (e de 6 em 6 horas) a Pinkie
# relê o canal do começo ao fim e completa o que estiver faltando no /data —
# então, mesmo se o volume for apagado, ela não esquece de ninguém.
#
# Regra de ouro: o que já está no /data NUNCA é sobrescrito pelo histórico,
# o histórico só preenche quem estiver faltando.

_RE_DATA_EM_EMBED = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})")
_RE_MENCAO_EM_TEXTO = re.compile(r"<@!?(\d+)>")


def _verificar_armazenamento_aniversario() -> None:
    """Log claro de onde os aniversários estão sendo salvos e se dá pra gravar."""
    pasta = os.path.dirname(_ANIVERSARIO_DATA_PATH) or "."
    try:
        os.makedirs(pasta, exist_ok=True)
        teste = os.path.join(pasta, ".pinkie_teste_escrita")
        with open(teste, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(teste)
        print(f"[pinkie-aniversario] salvando aniversários em {_ANIVERSARIO_DATA_PATH} ✅")
    except OSError as e:
        print(
            f"[pinkie-aniversario] ⚠️ NÃO consigo gravar em {pasta!r}: {e!r} — "
            f"monta um Volume nesse caminho. Enquanto isso o bot se vira relendo o "
            f"histórico do canal, mas o certo é o /data funcionar."
        )


def _tipo_embed_aniversario(embed: discord.Embed):
    """'registrado', 'atualizado' ou 'parabens' se o embed for de um desses
    eventos; None caso contrário."""
    titulo = _normalizar(embed.title or "")
    if "aniversario registrado" in titulo:
        return "registrado"
    if "aniversario atualizado" in titulo:
        return "atualizado"
    if "feliz aniversario" in titulo:
        return "parabens"
    return None


async def _autor_do_evento(msg: discord.Message, embed: discord.Embed):
    """Descobre de QUEM é o evento: pela @menção no embed ou, se não tiver
    (caso do 'Atualizado' de outros bots), pela mensagem à qual o bot respondeu."""
    achou = _RE_MENCAO_EM_TEXTO.search(embed.description or "")
    if achou:
        return int(achou.group(1))

    ref = msg.reference
    if ref is None:
        return None
    original = ref.resolved or ref.cached_message
    if not isinstance(original, discord.Message) and ref.message_id:
        try:
            original = await msg.channel.fetch_message(ref.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
    if isinstance(original, discord.Message) and not original.author.bot:
        return original.author.id
    return None


async def _ler_historico_aniversarios():
    """Relê o canal de aniversários do começo ao fim, em ordem cronológica, e
    devolve (aniversarios, parabens, qtd_mensagens) com o que dá pra deduzir:

      • embed 'Registrado'/'Atualizado' → vale a data que está nele;
      • mensagem de pessoa só com uma data → vale SÓ se essa pessoa ainda não
        tinha nenhuma (mudança de data exige confirmação, então uma data nova
        sozinha não troca nada);
      • embed 'Feliz Aniversário' → marca o ano em que a pessoa já foi parabenizada.
    """
    canal = await _garantir_canal(CANAL_ANIVERSARIO_ID)
    if canal is None or not hasattr(canal, "history"):
        print(f"[pinkie-aniversario] não achei o canal {CANAL_ANIVERSARIO_ID} pra reler o histórico.")
        return None

    aniversarios = {}
    parabens = {}
    lidas = 0

    try:
        async for msg in canal.history(limit=None, oldest_first=True):
            lidas += 1

            if not msg.author.bot:
                data = _parse_aniversario(msg.content or "")
                if data and str(msg.author.id) not in aniversarios:
                    aniversarios[str(msg.author.id)] = {"dia": data[0], "mes": data[1]}
                continue

            if not msg.embeds:
                continue
            embed = msg.embeds[0]
            tipo = _tipo_embed_aniversario(embed)
            if tipo is None:
                continue

            uid = await _autor_do_evento(msg, embed)
            if uid is None:
                continue

            if tipo == "parabens":
                ano = msg.created_at.astimezone(_FUSO_ANIVERSARIO).year
                parabens[str(uid)] = max(ano, int(parabens.get(str(uid), 0)))
                continue

            achou = _RE_DATA_EM_EMBED.search(embed.description or "")
            if not achou:
                continue
            dia, mes = int(achou.group(1)), int(achou.group(2))
            try:
                date(2000, mes, dia)
            except ValueError:
                continue
            aniversarios[str(uid)] = {"dia": dia, "mes": mes}
    except (discord.Forbidden, discord.HTTPException) as e:
        print(
            f"[pinkie-aniversario] ⚠️ parei de ler o histórico no meio ({e!r}) — o bot "
            f"precisa da permissão 'Ler Histórico de Mensagens' no canal. Usando o que deu pra ler."
        )

    return aniversarios, parabens, lidas


async def _sincronizar_aniversarios_do_historico() -> None:
    """Lê o canal e completa o /data com quem estiver faltando. Nunca
    sobrescreve o que já está salvo."""
    resultado = await _ler_historico_aniversarios()
    if resultado is None:
        return
    aniversarios, parabens, lidas = resultado

    # Daqui pra baixo NÃO tem nenhum await de propósito: carrega, mescla e salva
    # tudo de uma vez, assim um registro feito ao vivo durante a leitura não se perde.
    dados = _carregar_dados_aniversario()
    novos = 0
    for uid, reg in aniversarios.items():
        if uid not in dados["aniversarios"]:
            dados["aniversarios"][uid] = reg
            novos += 1

    parabens_novos = 0
    for uid, ano in parabens.items():
        atual = int(dados["parabens"].get(uid, 0) or 0)
        if ano > atual:
            dados["parabens"][uid] = str(ano)
            parabens_novos += 1

    if novos or parabens_novos:
        _salvar_dados_aniversario(dados)
    print(
        f"[pinkie-aniversario] li {lidas} mensagens do canal: {novos} aniversário(s) "
        f"recuperado(s), {parabens_novos} parabéns já dados reconhecido(s). "
        f"Total salvo: {len(dados['aniversarios'])}."
    )


@tasks.loop(hours=6)
async def _ressincronizar_aniversarios():
    """De 6 em 6 horas relê o canal (pega o que foi mandado enquanto o bot
    estava fora do ar, por exemplo). A 1ª execução é pulada porque o on_ready
    já acabou de fazer a leitura completa."""
    if _ressincronizar_aniversarios.current_loop == 0:
        return
    try:
        await _sincronizar_aniversarios_do_historico()
    except Exception as e:
        print(f"[pinkie-aniversario] erro ao reler o histórico: {e!r}")


# ══════════════════════════════════════════════════════════════════
# CARTA SURPRESA DA PINKIE — formulário + revisão da staff
#
# Painel fixo (embed + botão "💌 Escrever Carta") em
# CANAL_PAINEL_CARTA_ID. Quem clica escolhe primeiro se quer publicar
# com o nome ou anônimo, depois escreve o texto num modal.
#
# A carta cai em CANAL_REVISAO_CARTA_ID — SEMPRE com o nick e o ID de
# quem mandou, mesmo se a pessoa pediu anonimato (isso só vale pra
# quando a carta for publicada de verdade depois; a staff nunca perde
# o rastro de quem escreveu, pra fins de moderação). A Pinkie já reage
# na hora com ✅ e ❌, e a votação é feita REAGINDO em cima dessas duas
# — sem botão. Só quem é staff (CARGOS_STAFF_IDS) tem o voto contado;
# reação de qualquer outra pessoa é removida na hora. A decisão fica
# registrada ali (quem decidiu e quando), a mensagem nunca é apagada
# e as reações são limpas depois de decidida, pra travar o resultado.
#
# Quando aceita, a carta é publicada de verdade em
# CANAL_PUBLICACAO_CARTA_ID, num embed bonito e sem pingar ninguém —
# se a pessoa escolheu anônima, não aparece nome nem ID nenhum ali; só
# se ela escolheu "com o nome" é que o nome aparece (como texto puro,
# nunca como @menção/ping).
# ══════════════════════════════════════════════════════════════════

def _carregar_dados_carta() -> dict:
    try:
        with open(_CARTA_DATA_PATH, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except FileNotFoundError:
        print(
            f"[pinkie-carta] {_CARTA_DATA_PATH} não existe ainda (primeira vez, ou o "
            f"volume persistente não tá montado nesse caminho) — começando do zero."
        )
        dados = {}
    except json.JSONDecodeError as e:
        print(f"[pinkie-carta] {_CARTA_DATA_PATH} tá corrompido ({e!r}) — começando do zero.")
        dados = {}
    dados.setdefault("painel_mensagem_id", None)
    dados.setdefault("cartas", {})
    return dados


def _salvar_dados_carta(dados: dict) -> None:
    """Grava o JSON em disco. Se isso falhar silenciosamente (ex.: Railway sem
    Volume persistente montado em _CARTA_DATA_PATH), o painel/cartas somem a
    cada deploy — por isso o print de erro é bem explícito."""
    try:
        pasta = os.path.dirname(_CARTA_DATA_PATH)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        with open(_CARTA_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(
            f"[pinkie-carta] ⚠️ NÃO CONSEGUI SALVAR {_CARTA_DATA_PATH}: {e!r} — "
            f"confere se existe um Volume do Railway montado exatamente nesse "
            f"caminho, senão o painel vai duplicar a cada deploy."
        )


def _gerar_id_carta() -> str:
    return uuid.uuid4().hex[:10]


def _achar_carta_por_mensagem(dados: dict, mensagem_id: int):
    """Varre as cartas salvas e devolve (carta_id, registro) da que bate com
    esse ID de mensagem no canal de revisão. None, None se não achar."""
    for carta_id, registro in dados.get("cartas", {}).items():
        if registro.get("mensagem_id") == mensagem_id:
            return carta_id, registro
    return None, None


def _embed_carta(registro: dict, decidido_por: discord.Member = None) -> discord.Embed:
    """Monta (ou remonta, depois de decidida) o embed de UMA carta no canal de
    revisão, sempre a partir do que foi salvo em disco — nick, ID e texto ficam
    gravados na hora do envio, então o embed nunca depende de a pessoa ainda
    estar no servidor ou de buscar o membro de novo."""
    cores = {"pendente": COR_PINKIE, "aceita": discord.Colour.green(), "recusada": discord.Colour.red()}
    status = registro.get("status", "pendente")

    embed = discord.Embed(
        title="🎉 Carta Surpresa da Pinkie!",
        description=registro["texto"],
        color=cores.get(status, COR_PINKIE),
    )
    if registro.get("autor_avatar_url"):
        embed.set_thumbnail(url=registro["autor_avatar_url"])

    embed.add_field(
        name="✍️ Quem escreveu",
        value=f"<@{registro['autor_id']}>\n`{registro['autor_nome']}`\nID: `{registro['autor_id']}`",
        inline=True,
    )
    embed.add_field(
        name="🎭 Publicar como",
        value="Anônima (máscara de palhaço)" if registro.get("anonimo") else "Com o nome",
        inline=True,
    )

    quem_decidiu = (
        decidido_por.mention if decidido_por
        else (f"<@{registro['decidido_por']}>" if registro.get("decidido_por") else "a staff")
    )
    if status == "pendente":
        embed.add_field(
            name="Status",
            value=(
                f"⏳ Esperando a staff reagir com {EMOJI_ACEITAR} (aceitar) "
                f"ou {EMOJI_RECUSAR} (recusar)"
            ),
            inline=False,
        )
    elif status == "aceita":
        embed.add_field(name="Status", value=f"✅ Aceita por {quem_decidiu} — CONFETE! 🎊", inline=False)
    else:
        embed.add_field(name="Status", value=f"❌ Recusada por {quem_decidiu}", inline=False)

    embed.set_footer(text="🎪 Pinkie Pie  •  Carta Surpresa")
    return embed


def _embed_publicacao_carta(registro: dict) -> discord.Embed:
    """Embed 'bonito' pra carta já aceita, publicado no canal público
    (CANAL_PUBLICACAO_CARTA_ID). NUNCA usa @menção — texto puro, no máximo —
    e só mostra qualquer identificação de quem escreveu se a pessoa NÃO
    marcou anônimo. Se marcou anônimo, não aparece nome, avatar nem ID."""
    anonimo = registro.get("anonimo", False)

    embed = discord.Embed(
        title="💌 Uma Carta Surpresa chegou!",
        description=registro["texto"],
        color=COR_PINKIE,
    )

    if anonimo:
        embed.set_author(name="Remetente misterioso 🎭")
    else:
        # Nome como texto puro (nunca <@id>/mention) — sem pingar ninguém.
        avatar_url = registro.get("autor_avatar_url")
        if avatar_url:
            embed.set_author(name=f"De: {registro.get('autor_nome', 'alguém do servidor')}", icon_url=avatar_url)
        else:
            embed.set_author(name=f"De: {registro.get('autor_nome', 'alguém do servidor')}")

    embed.set_footer(text="🎪 Pinkie Pie  •  Carta Surpresa")
    return embed


async def _publicar_carta_aceita(registro: dict) -> None:
    """Quando a staff aceita uma carta, publica ela (no formato bonito, sem
    pingar ninguém) no canal público. Se o canal não estiver configurado ou
    não for encontrado, só registra no log e segue a vida — a decisão em si
    já foi salva de qualquer forma."""
    if not CANAL_PUBLICACAO_CARTA_ID:
        print("[pinkie-carta] CANAL_PUBLICACAO_CARTA_ID não configurado — pulei a publicação pública.")
        return

    canal = await _garantir_canal(CANAL_PUBLICACAO_CARTA_ID)
    if canal is None:
        print(f"[pinkie-carta] não encontrei o canal de publicação {CANAL_PUBLICACAO_CARTA_ID}.")
        return

    embed = _embed_publicacao_carta(registro)
    try:
        await canal.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[pinkie-carta] não consegui publicar a carta aceita no canal público: {e!r}")


async def _registrar_carta(interaction: discord.Interaction, texto: str, anonimo: bool) -> None:
    """Roda quando alguém envia o modal da carta: publica no canal de revisão
    (sempre com nick + ID), já reage com ✅/❌ pra votação, e salva o registro
    em disco."""
    guild = interaction.guild
    if guild is None:
        return

    canal = await _garantir_canal(CANAL_REVISAO_CARTA_ID)
    if canal is None:
        await interaction.response.send_message(
            "Ops, não achei o canal de revisão! chama a staff que eu já fico by aqui. 🎈",
            ephemeral=True,
        )
        return

    carta_id = _gerar_id_carta()
    registro = {
        "guild_id": guild.id,
        "canal_id": canal.id,
        "mensagem_id": None,
        "autor_id": interaction.user.id,
        "autor_nome": str(interaction.user),
        "autor_avatar_url": interaction.user.display_avatar.url,
        "texto": texto,
        "anonimo": anonimo,
        "status": "pendente",
        "decidido_por": None,
        "decidido_em": None,
        "criado_em": time.time(),
    }

    embed = _embed_carta(registro)

    try:
        mensagem = await canal.send(embed=embed)
    except discord.HTTPException:
        await interaction.response.send_message(
            "Escorreguei numa casca de banana e sua carta não foi. Tenta de novo? 🍌",
            ephemeral=True,
        )
        return

    # Já deixa as duas reações prontas pra staff votar.
    try:
        await mensagem.add_reaction(EMOJI_ACEITAR)
        await mensagem.add_reaction(EMOJI_RECUSAR)
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[pinkie-carta] não consegui reagir na carta {carta_id}: {e!r}")

    registro["mensagem_id"] = mensagem.id

    dados = _carregar_dados_carta()
    dados.setdefault("cartas", {})[carta_id] = registro
    _salvar_dados_carta(dados)

    await interaction.response.send_message(
        "Carta enviada! 🎉 vou guardar ela com carinho (e um pouquinho de purpurina) até "
        "a staff decidir — eu não prometo pressa, só prometo que alguém vai ler.",
        ephemeral=True,
    )


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """Escuta as reações no canal de revisão da carta. Só ✅/❌ importam, só
    staff tem voto contado (reação de qualquer outra pessoa é removida na
    hora), e só a primeira decisão vale — depois disso a carta trava."""
    if payload.channel_id != CANAL_REVISAO_CARTA_ID:
        return
    if payload.member is None or payload.member.bot:
        return

    emoji = str(payload.emoji)
    if emoji not in (EMOJI_ACEITAR, EMOJI_RECUSAR):
        return

    dados = _carregar_dados_carta()
    carta_id, registro = _achar_carta_por_mensagem(dados, payload.message_id)
    if registro is None:
        return  # reação em alguma outra mensagem do canal, não é carta

    canal = await _garantir_canal(payload.channel_id)
    if canal is None:
        return

    membro = payload.member

    if not _e_staff(membro):
        # Reação de quem não é staff não conta — some com ela.
        try:
            mensagem = await canal.fetch_message(payload.message_id)
            await mensagem.remove_reaction(payload.emoji, membro)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
        return

    if registro.get("status") != "pendente":
        # Carta já foi decidida antes — tira a reação atrasada também.
        try:
            mensagem = await canal.fetch_message(payload.message_id)
            await mensagem.remove_reaction(payload.emoji, membro)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
        return

    resposta = "aceita" if emoji == EMOJI_ACEITAR else "recusada"
    registro["status"] = resposta
    registro["decidido_por"] = membro.id
    registro["decidido_em"] = time.time()
    _salvar_dados_carta(dados)

    try:
        mensagem = await canal.fetch_message(payload.message_id)
        embed = _embed_carta(registro, decidido_por=membro)
        await mensagem.edit(embed=embed)
        # Limpa as reações pra travar visualmente o resultado (ninguém mais
        # consegue votar em cima de uma carta já decidida).
        await mensagem.clear_reactions()
    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
        print(f"[pinkie-carta] não consegui atualizar a carta {carta_id} após decisão: {e!r}")

    if resposta == "aceita":
        await _publicar_carta_aceita(registro)


class ModalCarta(discord.ui.Modal, title="Carta Surpresa da Pinkie"):
    """Ficha preenchida por quem já escolheu anônimo ou com nome."""

    carta = discord.ui.TextInput(
        label="Sua carta",
        style=discord.TextStyle.paragraph,
        placeholder="Um desabafo, uma piada, uma zoeira de leve, um agradecimento... solta o verbo!",
        max_length=3500,
        required=True,
    )

    def __init__(self, anonimo: bool):
        super().__init__()
        self.anonimo = anonimo

    async def on_submit(self, interaction: discord.Interaction):
        await _registrar_carta(interaction, str(self.carta), self.anonimo)


class _ViewEscolherAnonimato(discord.ui.View):
    """View efêmera (não precisa sobreviver restart) que aparece depois de
    clicar em "Escrever Carta" no painel — pergunta se a pessoa quer aparecer
    com o nome ou anônima antes de abrir o modal de verdade."""

    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Anônima", emoji="🎭", style=discord.ButtonStyle.secondary)
    async def anonima(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalCarta(anonimo=True))

    @discord.ui.button(label="Com meu nome", emoji="📝", style=discord.ButtonStyle.secondary)
    async def com_nome(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalCarta(anonimo=False))


class PainelCarta(discord.ui.View):
    """View fixa do painel — só o botão que abre a escolha de anonimato, que
    por sua vez abre o modal com o texto da carta."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Escrever Carta",
        emoji="💌",
        style=discord.ButtonStyle.primary,
        custom_id="pinkie_carta_escrever",
    )
    async def escrever(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Antes de escrever: quer aparecer com o seu nome, ou de máscara de palhaço "
            "(anônima)? 🎭",
            view=_ViewEscolherAnonimato(),
            ephemeral=True,
        )


async def _configurar_painel_carta() -> str:
    """Publica ou atualiza o painel fixo da Carta Surpresa no canal configurado.
    Retorna uma mensagem de status (sucesso ou o motivo de ter pulado), pra dar
    pra usar tanto no print do on_ready quanto na resposta de um comando manual."""
    if not CANAL_PAINEL_CARTA_ID:
        return "CANAL_PAINEL_CARTA_ID não configurado (ainda tá com o valor de exemplo) — pulei o painel."

    canal = await _garantir_canal(CANAL_PAINEL_CARTA_ID)
    if canal is None:
        return (
            f"não encontrei nenhum canal com o ID {CANAL_PAINEL_CARTA_ID}. Confere se "
            f"esse é mesmo o ID do canal #crm (clique direito no canal > Copiar ID do "
            f"Canal, com o Modo Desenvolvedor ativado) e se o bot tem o cargo/permissão "
            f"pra ENXERGAR esse canal."
        )

    embed = discord.Embed(
        title="🎉 Carta Surpresa da Pinkie!",
        description=(
            "Psiu! 💌 Às vezes bate aquela vontade de colocar em palavras o que a gente "
            "tá sentindo — um desabafo, uma reflexão, um agradecimento, ou uma mensagem "
            "pra alguém especial. Não existe sentimento certo ou errado pra compartilhar, "
            "e às vezes uma cartinha sua pode tocar o coração de quem precisava ler "
            "exatamente aquilo.\n\n"
            "Clica no botão abaixo, escolhe se quer aparecer com o seu nome ou de "
            "máscara de palhaço (anônima), e escreve sua carta com carinho. A staff dá "
            "uma olhadinha antes de soltar no mundo. 🎪\n\n"
            "🤡 **Pinkie:** pode escrever sem medo — eu vou guardar cada cartinha com "
            "todo cuidado. Só prometo uma coisa: alguém vai ler. 💕"
        ),
        color=COR_PINKIE,
    )
    if IMAGEM_PAINEL_CARTA_URL:
        embed.set_image(url=IMAGEM_PAINEL_CARTA_URL)
    embed.set_footer(text="🎪 Pinkie Pie  •  Carta Surpresa")

    dados = _carregar_dados_carta()
    try:
        mensagem = await _publicar_ou_reaproveitar_painel(
            canal, dados, "painel_mensagem_id", embed, PainelCarta()
        )
    except discord.Forbidden:
        return (
            f"achei o canal #{canal.name}, mas não tenho permissão pra enviar/editar "
            f"mensagem lá. Dá pro bot as permissões Ver Canal, Enviar Mensagens, "
            f"Inserir Links e Usar Botões nesse canal."
        )

    dados["painel_mensagem_id"] = mensagem.id
    _salvar_dados_carta(dados)
    return f"painel publicado/atualizado em #{canal.name}! ✅"


# ══════════════════════════════════════════════════════════════════
# BOOTSTRAP
# ══════════════════════════════════════════════════════════════════

def main():
    if not TOKEN:
        raise SystemExit(
            "Faltou o DISCORD_TOKEN! Cria um arquivo .env do lado desse bot.py com:\n"
            "DISCORD_TOKEN=seu_token_aqui"
        )
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
