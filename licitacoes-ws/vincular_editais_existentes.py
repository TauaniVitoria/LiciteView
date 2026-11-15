"""Cria os vínculos usuário–edital para editais processados antes da tabela usuario_edital.

Um usuário é considerado ligado a um edital se já recebeu uma notificação, fez uma
análise de viabilidade ou fez uma pergunta sobre ele. Editais sem nenhum desses
registros ficam sem vínculo e voltam ao histórico de quem abri-los de novo pela busca.

Pode ser executado mais de uma vez: só cria os vínculos que faltam. Rode após a
migration 004 e novamente ao publicar o backend novo, para cobrir editais processados
nesse intervalo pelo backend antigo.

Uso:  python vincular_editais_existentes.py
"""
from database import SessionLocal
from models import AnaliseViabilidade, Notificacao, PerguntaEdital, UsuarioEdital


def main() -> None:
    with SessionLocal() as session:
        pares: set[tuple] = set()
        for modelo in (Notificacao, AnaliseViabilidade, PerguntaEdital):
            linhas = (
                session.query(modelo.usuario_id, modelo.edital_id)
                .filter(modelo.edital_id.isnot(None))
                .distinct()
                .all()
            )
            pares.update((u, e) for u, e in linhas)

        existentes = {(v.usuario_id, v.edital_id) for v in session.query(UsuarioEdital).all()}
        novos = pares - existentes
        for usuario_id, edital_id in novos:
            session.add(UsuarioEdital(usuario_id=usuario_id, edital_id=edital_id))
        session.commit()
        print(f"Vínculos encontrados: {len(pares)} | já existiam: {len(pares & existentes)} | criados: {len(novos)}")


if __name__ == "__main__":
    main()
