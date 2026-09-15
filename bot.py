"""
🎪 PINKIE PIE — Bot da CRM
══════════════════════════════════════════════════════════════════
Bot de Discord (discord.py) com a personalidade da Pinkie Pie:
alegre, travessa e engraçadinha — a palhaça oficial do servidor CRM.

Já vem com o sistema de "Carta Surpresa da Pinkie" integrado: um
formulário onde qualquer um pode escrever uma cartinha (com nome ou
anônima), que cai num canal de revisão pra staff aprovar ou recusar
antes de ir pro mundo.

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

import json
import os
import random
import time
import uuid

import discord
from discord.ext import commands

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ══════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO GERAL — TROQUE AQUI pelos dados reais do servidor CRM
# ══════════════════════════════════════════════════════════════════

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIXO = "pk!"

# Rosa-choque bem "Pinkie" pros embeds
COR_PINKIE = discord.Colour.from_rgb(255, 105, 180)

# Cargos que contam como staff (administrator sempre conta também)
CARGOS_STAFF_IDS = [
    111111111111111111,  # TROQUE AQUI — cargo de staff nº1 da CRM
    222222222222222222,  # TROQUE AQUI — cargo de staff nº2 da CRM (se tiver)
]

# Canais do sistema de Carta Surpresa
CANAL_PAINEL_CARTA_ID = 333333333333333333   # TROQUE AQUI — onde fica o painel fixo
CANAL_REVISAO_CARTA_ID = 444444444444444444  # TROQUE AQUI — onde a staff avalia as cartas

_CARTA_DATA_PATH = os.getenv("PINKIE_CARTA_DATA_PATH", "/data/pinkie_carta.json")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

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


def frase_aleatoria(lista: list) -> str:
    return random.choice(lista)


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


async def _publicar_ou_reaproveitar_painel(
    canal, dados: dict, chave_id: str, embed: discord.Embed, view: discord.ui.View
):
    """Edita a mensagem do painel se ela ainda existir; senão manda uma nova."""
    mensagem_id = dados.get(chave_id)
    if mensagem_id:
        try:
            mensagem = await canal.fetch_message(mensagem_id)
            await mensagem.edit(embed=embed, view=view)
            return mensagem
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
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
        dados_cartas = _carregar_dados_carta()
        for carta_id, registro in dados_cartas.get("cartas", {}).items():
            if registro.get("status") == "pendente":
                bot.add_view(_ViewVotarCarta(carta_id))
        status = await _configurar_painel_carta()
        print(f"[pinkie-carta] {status}")
    except Exception as e:
        print(f"[pinkie-carta] erro ao configurar o painel da carta surpresa: {e!r}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    await bot.process_commands(message)


@bot.command(name="oi")
async def cmd_oi(ctx: commands.Context):
    await ctx.reply(
        f"OIOIOI {ctx.author.mention}! 🎉 bem-vindo(a) ao meu picadeiro particular. "
        f"digita `{PREFIXO}piada` se quiser rir (ou gemer, sem julgamento)."
    )


@bot.command(name="piada")
async def cmd_piada(ctx: commands.Context):
    await ctx.reply(f"🤡 {frase_aleatoria(FRASES_PIADA)}")


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
# CARTA SURPRESA DA PINKIE — formulário + revisão da staff
#
# Painel fixo (embed + botão "💌 Escrever Carta") em
# CANAL_PAINEL_CARTA_ID. Quem clica escolhe primeiro se quer publicar
# com o nome ou anônimo, depois escreve o texto num modal.
#
# A carta cai em CANAL_REVISAO_CARTA_ID — SEMPRE com o nick e o ID de
# quem mandou, mesmo se a pessoa pediu anonimato (isso só vale pra
# quando a carta for publicada de verdade depois; a staff nunca perde
# o rastro de quem escreveu, pra fins de moderação) — junto com dois
# botões, ✅ Aceitar e ❌ Recusar, só pra staff (CARGOS_STAFF_IDS). A
# decisão fica registrada ali (quem decidiu e quando), a mensagem
# nunca é apagada.
# ══════════════════════════════════════════════════════════════════

def _carregar_dados_carta() -> dict:
    try:
        with open(_CARTA_DATA_PATH, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        dados = {}
    dados.setdefault("painel_mensagem_id", None)
    dados.setdefault("cartas", {})
    return dados


def _salvar_dados_carta(dados: dict) -> None:
    try:
        pasta = os.path.dirname(_CARTA_DATA_PATH)
        if pasta:
            os.makedirs(pasta, exist_ok=True)
        with open(_CARTA_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[pinkie-carta] não consegui salvar {_CARTA_DATA_PATH}: {e!r}")


def _gerar_id_carta() -> str:
    return uuid.uuid4().hex[:10]


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
        embed.add_field(name="Status", value="⏳ Esperando a Pinkie (e a staff) darem o veredito", inline=False)
    elif status == "aceita":
        embed.add_field(name="Status", value=f"✅ Aceita por {quem_decidiu} — CONFETE! 🎊", inline=False)
    else:
        embed.add_field(name="Status", value=f"❌ Recusada por {quem_decidiu}", inline=False)

    embed.set_footer(text="🎪 Pinkie Pie  •  Carta Surpresa")
    return embed


async def _registrar_carta(interaction: discord.Interaction, texto: str, anonimo: bool) -> None:
    """Roda quando alguém envia o modal da carta: publica no canal de revisão
    (sempre com nick + ID) e salva o registro em disco."""
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
    view = _ViewVotarCarta(carta_id)

    try:
        mensagem = await canal.send(embed=embed, view=view)
    except discord.HTTPException:
        await interaction.response.send_message(
            "Escorreguei numa casca de banana e sua carta não foi. Tenta de novo? 🍌",
            ephemeral=True,
        )
        return

    registro["mensagem_id"] = mensagem.id

    dados = _carregar_dados_carta()
    dados.setdefault("cartas", {})[carta_id] = registro
    _salvar_dados_carta(dados)

    await interaction.response.send_message(
        "Carta enviada! 🎉 vou guardar ela com carinho (e um pouquinho de purpurina) até "
        "a staff decidir — eu não prometo pressa, só prometo que alguém vai ler.",
        ephemeral=True,
    )


async def _responder_carta(interaction: discord.Interaction, carta_id: str, resposta: str) -> None:
    """Roda quando a staff clica em ✅ Aceitar ou ❌ Recusar numa carta. resposta
    é 'aceita' ou 'recusada'. Só decide na primeira vez — depois disso a decisão
    fica travada e registrada ali."""
    if not isinstance(interaction.user, discord.Member) or not _e_staff(interaction.user):
        await interaction.response.send_message(
            "Ei ei ei, só a staff pode dar o veredito nessa cartinha! 🎪", ephemeral=True
        )
        return

    dados = _carregar_dados_carta()
    registro = dados.get("cartas", {}).get(carta_id)
    if registro is None:
        await interaction.response.send_message("Hmm, essa carta sumiu igual mágica de palhaço. Não existe mais.", ephemeral=True)
        return

    if registro.get("status") != "pendente":
        await interaction.response.send_message(
            "Essa carta já foi avaliada por outra pessoa da staff — chegou atrasado no circo! 🎟️",
            ephemeral=True,
        )
        return

    registro["status"] = resposta
    registro["decidido_por"] = interaction.user.id
    registro["decidido_em"] = time.time()
    _salvar_dados_carta(dados)

    embed = _embed_carta(registro, decidido_por=interaction.user)

    view = interaction.view
    for item in view.children:
        item.disabled = True

    await interaction.response.edit_message(embed=embed, view=view)


class _ViewVotarCarta(discord.ui.View):
    """Botões ✅ Aceitar / ❌ Recusar de UMA carta específica — o custom_id
    carrega o ID da carta, então precisa ser recriada (e re-registrada) pra
    cada carta ainda pendente sempre que o bot reinicia."""

    def __init__(self, carta_id: str):
        super().__init__(timeout=None)
        self.carta_id = carta_id

        botao_aceitar = discord.ui.Button(
            label="Aceitar",
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id=f"pinkie_carta_aceitar:{carta_id}",
        )
        botao_aceitar.callback = self._aceitar
        self.add_item(botao_aceitar)

        botao_recusar = discord.ui.Button(
            label="Recusar",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id=f"pinkie_carta_recusar:{carta_id}",
        )
        botao_recusar.callback = self._recusar
        self.add_item(botao_recusar)

    async def _aceitar(self, interaction: discord.Interaction):
        await _responder_carta(interaction, self.carta_id, "aceita")

    async def _recusar(self, interaction: discord.Interaction):
        await _responder_carta(interaction, self.carta_id, "recusada")


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
            "Psiu! 🎈 Às vezes bate aquela vontade de escrever alguma coisa — um "
            "desabafo, uma piada, um agradecimento ou só uma zoeira de leve — e essa "
            "cartinha pode até alegrar o dia de alguém.\n\n"
            "Clica no botão abaixo, escolhe se quer aparecer com o seu nome ou de "
            "máscara de palhaço (anônima), e escreve sua carta. A staff dá uma "
            "olhadinha antes de soltar no mundo. 🎪\n\n"
            "🤡 **Pinkie:** ...eu não prometo que não vou rir. Só prometo que alguém vai ler!"
        ),
        color=COR_PINKIE,
    )
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
