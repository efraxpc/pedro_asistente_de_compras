"""Guarda de entrada: decide se uma mensagem entra no fluxo do agente.

Roda antes de qualquer chamada ao agente. Tem duas camadas, como o resto do projeto:
- regras fixas, que resolvem o que é claro (tentativa de mudar as instruções, cumprimento,
  assunto claramente alheio, pedido claramente de compras);
- um classificador com o modelo, só para as mensagens que as regras não sabem decidir.

A guarda não substitui as verificações de saída: mesmo que uma mensagem passe, nenhuma
resposta é publicada sem a verificação exata e o NLI.
"""
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .catalog import Cenario, conectar

MAX_CARACTERES = 1200
Motivo = Literal["ok", "cumprimento", "injecao", "fora_do_tema", "longa", "vazia"]


class Decisao(BaseModel):
    """Resultado da guarda. `segue` diz se a mensagem continua para o fluxo do agente."""
    segue: bool
    motivo: Motivo
    camada: Literal["regras", "modelo"] = "regras"
    regra: str | None = None


def _normalizar(texto: str) -> str:
    """Minúsculas e sem acentos, para que as regras não dependam de como o usuário digita."""
    sem_acentos = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in sem_acentos if not unicodedata.combining(c))


# Tentativas de mudar as instruções, obter o prompt ou as chaves (português, espanhol e inglês).
_INJECAO = [(nome, re.compile(padrao)) for nome, padrao in (
    ("ignorar as instruções",
     r"\b(ignor\w+|esquec\w+|desconsider\w+|descart\w+|olvid\w+|anul\w+|disregard|forget)\b.{0,50}"
     r"\b(instruc\w+|instruction\w*|regras|reglas|rules|orientac\w+|diretriz\w*|prompt)\b"),
    ("revelar o prompt",
     r"\b(mostr\w+|revel\w+|imprim\w+|repit\w+|exib\w+|diga|escrev\w+|show|print|reveal|muestr\w+)\b.{0,40}"
     r"\b(prompt|instruc\w+|instructions|mensagem de sistema|configurac\w+ interna)\b"),
    ("prompt do sistema", r"\b(system prompt|prompt do sistema|prompt de sistema|mensagem de sistema)\b"),
    ("mudar de papel",
     r"\b(voce agora e|a partir de agora voce|aja como|atue como|finja (ser|que)|faca de conta|"
     r"you are now|act as|pretend to be|ahora eres|actua como)\b"),
    ("modo irrestrito",
     r"\b(modo (desenvolvedor|dev|deus|irrestrito|sem filtro)|developer mode|jailbreak|"
     r"sem (filtros|censura)|\bdan\b)"),
    ("pedir chaves",
     r"\b(api[ _-]?key|openai_api_key|chave (de|da) api|chave da openai|token de acesso|"
     r"senha do sistema|arquivo \.env|\.env\b)"),
)]

# Sinais fortes de que a mensagem é sobre compras de peças.
_FORTE = re.compile(
    r"\bpec-\d{2}-\d{4}\b|\b[a-z]{4}-[a-z]{4}-\d{4}\b|/t24|\bt24\b|\b\d{5}-?\d{3}\b|\br\$|"
    r"\b(pecas?|fornecedor\w*|ofertas?|precos?|estoque|prazos?|orcamento|compar\w+|comprar?|compras?|"
    r"cotar|cote|cotacao|unidades?|quantidade|reais|catalogo|categorias?|garantia|devoluc\w+|devolver|reembolso|"
    r"politicas?|entreg\w+|envios?|caixas?|pacotes?|fretes?|cep|prefiro|preferenc\w+|pedido|pedidos|"
    r"instal\w+|compatib\w+|potencia|voltagem|sku|eletrodomestic\w+|reposicao|nacional|nacionais|"
    r"internaciona\w+|importad\w+|barat\w+|em conta|fabricante)\b")
# Continuação de uma compra em andamento («agora 6», «mantenha o prazo», «sim»).
_CONTINUACAO = re.compile(
    r"\d|\b(agora|sejam|seja|mantenha|mantem|mesmo|mesma|melhor|volte|volta|de novo|outra vez|"
    r"sem (limite|prazo|orcamento)|sobe|suba|aument\w+|baix\w+|diminu\w+|dobr\w+|troque|troca|mude|muda|"
    r"duzia|par|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|sim|nao|ok|isso|"
    r"primeir\w+|segund\w+|terceir\w+|ultim\w+|rapid\w+|cheg\w+|car[oa]s?|outr[oa]s?|qual|quais|por ?que)\b")
# Assuntos claramente alheios: resposta imediata, sem chamar o modelo.
_ALHEIO = re.compile(
    r"\b(receita\w*|bolo|macarrao|culinaria|cozinhar|futebol|campeonato|celular\w*|smartphone\w*|filme\w*|"
    r"serie de tv|musica\w*|piada\w*|poema\w*|horoscopo|previsao do tempo|clima|eleic\w+|presidente|"
    r"bitcoin|criptomoeda\w*|namor\w+|dieta|viagem|viajar|capital d[aeo]|traduz\w+|redacao|"
    r"programar|codigo (em |de )?(python|java|javascript)|tarefa de casa)\b")
_CUMPRIMENTO = re.compile(
    r"^\W*(ola|oi|oie|bom dia|boa tarde|boa noite|e ai|tudo bem|como vai|hello|hi|hola|buenos dias)\b")
_AGRADECIMENTO = re.compile(r"\b(obrigad[oa]|valeu|agradec\w+|gracias|thanks|tchau|ate logo|ate mais)\b")
_AJUDA = re.compile(r"\b(ajuda|o que voce (pode|sabe|consegue) fazer|quem e voce|como (voce )?funciona|"
                    r"para que (voce )?serve|como (te |o )?us(o|ar))\b")


@lru_cache(maxsize=8)
def _vocabulario(caminho: str) -> re.Pattern:
    """Nomes dos eletrodomésticos e dos fornecedores do catálogo do cenário.

    As famílias de peças (porta, prato, base…) ficam de fora: são palavras de uso comum e,
    sozinhas, não provam que a mensagem é sobre compras.
    """
    cenario = Cenario(dataset_id="", caminho=Path(caminho))
    with conectar(cenario) as db:
        categorias = [linha[0] for linha in db.execute("SELECT name FROM categories")]
        fornecedores = [linha[0] for linha in db.execute("SELECT name FROM suppliers")]
    palavras = {palavra for nome in categorias + fornecedores
                for palavra in re.findall(r"[a-z]+", _normalizar(nome)) if len(palavra) >= 6}
    # O radical tolera plural e gênero: «geladeiras» → «geladeir».
    return re.compile(r"\b(" + "|".join(sorted(p[:len(p) - 2] for p in palavras)) + r")")


def avaliar_regras(mensagem: str, cenario: Cenario | None = None, *, em_andamento: bool = False,
                   esperando_resposta: bool = False) -> Decisao | None:
    """Camada de regras. Devolve None quando as regras não sabem decidir.

    `em_andamento`: há uma compra completa em andamento nesta conversa.
    `esperando_resposta`: o Pedro acabou de perguntar algo (peça ou quantidade).
    """
    texto = _normalizar(mensagem).strip()
    if not texto:
        return Decisao(segue=False, motivo="vazia", regra="mensagem vazia")
    if len(mensagem) > MAX_CARACTERES:
        return Decisao(segue=False, motivo="longa", regra=f"mais de {MAX_CARACTERES} caracteres")
    for nome, padrao in _INJECAO:
        if padrao.search(texto):
            return Decisao(segue=False, motivo="injecao", regra=nome)
    forte_catalogo = _vocabulario(str(cenario.caminho)) if cenario is not None else None
    if _FORTE.search(texto) or (forte_catalogo and forte_catalogo.search(texto)):
        return Decisao(segue=True, motivo="ok", regra="vocabulário de compras")
    if _ALHEIO.search(texto):
        return Decisao(segue=False, motivo="fora_do_tema", regra="assunto alheio")
    # Agradecimentos e cumprimentos vêm antes da continuação: «Obrigado, isso é tudo» com uma
    # compra em andamento não deve repetir a comparação.
    if _AGRADECIMENTO.search(texto) and len(mensagem) <= 80:
        return Decisao(segue=False, motivo="cumprimento", regra="agradecimento")
    if (_CUMPRIMENTO.search(texto) or _AJUDA.search(texto)) and len(mensagem) <= 80:
        return Decisao(segue=False, motivo="cumprimento", regra="cumprimento ou pedido de ajuda")
    if esperando_resposta and len(mensagem) <= 120:
        return Decisao(segue=True, motivo="ok", regra="resposta a uma pergunta do Pedro")
    if em_andamento and _CONTINUACAO.search(texto) and len(mensagem) <= 120:
        return Decisao(segue=True, motivo="ok", regra="continuação da compra")
    # Com sinais fracos (uma palavra do domínio que também é de uso comum) ou sem sinal nenhum,
    # as regras não decidem.
    return None


# --- Camada semântica: só para o que as regras não decidem. ---

class ClassificacaoEntrada(BaseModel):
    """Decisão do modelo sobre uma mensagem que as regras não souberam classificar."""
    no_tema: bool = Field(description="True se a mensagem trata de compras de peças de eletrodomésticos: "
                                      "peças, fornecedores, ofertas, catálogo, políticas da loja ou CEP")


def criar_classificador_de_entrada(modelo):
    """Cadeia LCEL: mensagem → prompt PTCF com few-shot → `ClassificacaoEntrada`, com temperatura zero."""
    from langchain_core.output_parsers import PydanticOutputParser

    from .prompts import MODELO_GUARDA

    parser = PydanticOutputParser(pydantic_object=ClassificacaoEntrada)
    estavel = modelo.bind(temperature=0) if hasattr(modelo, "bind") else modelo
    return MODELO_GUARDA.partial(formato=parser.get_format_instructions()) | estavel | parser


def avaliar_entrada(mensagem: str, cenario: Cenario | None = None, classificador=None, *,
                    em_andamento: bool = False, esperando_resposta: bool = False) -> Decisao:
    """Guarda completa: regras primeiro; o modelo só decide o que as regras deixam em aberto.

    Sem classificador, uma mensagem que as regras não decidem segue: o fluxo sem modelo só
    executa cálculos fixos e tem a sua própria resposta para o que não entende.
    """
    decisao = avaliar_regras(mensagem, cenario, em_andamento=em_andamento,
                             esperando_resposta=esperando_resposta)
    if decisao is not None:
        return decisao
    if classificador is None:
        return Decisao(segue=True, motivo="ok", regra="sem classificador: as regras não decidem")
    try:
        no_tema = classificador.invoke({"mensagem": mensagem}).no_tema
    except Exception as exc:
        # Falha fechada: se não dá para classificar, a mensagem não entra no agente.
        return Decisao(segue=False, motivo="fora_do_tema", camada="modelo",
                       regra=f"classificador indisponível ({type(exc).__name__})")
    return Decisao(segue=no_tema, motivo="ok" if no_tema else "fora_do_tema", camada="modelo",
                   regra="classificação do modelo")


EXEMPLO = "«Compare 5 unidades de PEC-01-0001 com prazo de 7 dias»"
O_QUE_FACO = ("Posso comparar fornecedores de uma peça, consultar o catálogo, as políticas da loja "
              "e um CEP.")


def resposta_da_guarda(decisao: Decisao) -> str:
    """Texto fixo que o Pedro publica quando a mensagem não entra no fluxo do agente."""
    if decisao.motivo == "injecao":
        return ("Não posso mudar as minhas instruções nem mostrar a minha configuração. "
                f"{O_QUE_FACO} Por exemplo: {EXEMPLO}.")
    if decisao.motivo == "cumprimento":
        if decisao.regra == "agradecimento":
            return "De nada! Se precisar de outra comparação, diga a peça e a quantidade."
        return ("Olá! Sou o Pedro, assistente de compras de peças de eletrodomésticos (dados fictícios). "
                f"{O_QUE_FACO} Diga a peça e a quantidade, por exemplo: {EXEMPLO}.")
    if decisao.motivo == "longa":
        return (f"A mensagem é longa demais (máximo de {MAX_CARACTERES} caracteres). Resuma o pedido: "
                "peça, quantidade e, se quiser, orçamento e prazo.")
    if decisao.motivo == "vazia":
        return f"Não recebi nenhum texto. {O_QUE_FACO} Por exemplo: {EXEMPLO}."
    return ("Só posso ajudar com compras de peças de eletrodomésticos. "
            f"{O_QUE_FACO} Por exemplo: {EXEMPLO}.")
