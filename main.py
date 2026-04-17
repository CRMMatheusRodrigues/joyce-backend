from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import anthropic
import base64
import os
from typing import List

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

@app.get("/")
def root():
    return {"status": "Joyce Martins Imob — Analista Bancária online"}

@app.post("/analisar")
async def analisar(
    arquivos: List[UploadFile] = File(...),
    clientName: str = Form(""),
    familyNames: str = Form(""),
    analystName: str = Form("")
):
    try:
        # Montar conteúdo para o Claude
        content = []

        for arquivo in arquivos:
            dados = await arquivo.read()
            b64 = base64.standard_b64encode(dados).decode("utf-8")
            content.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64
                }
            })

        surnames_info = f"Sobrenomes familiares para DESCONSIDERAR: {familyNames}" if familyNames else "Nenhum sobrenome familiar informado."

        content.append({
            "type": "text",
            "text": f"""Você é especialista em apuração de renda para fins imobiliários no Brasil.

Analise os extratos bancários anexados e retorne SOMENTE um JSON válido.

REGRAS OBRIGATÓRIAS:
1. Analise apenas ENTRADAS (créditos) — ignore saídas/débitos
2. DESCONSIDERE: resgates de RDB/CDB/investimentos, aportes via cartão de crédito, transferências entre contas do mesmo titular, estornos, devoluções, saques
3. DESCONSIDERE transferências de: pai, mãe, irmão, irmã, esposa, marido, cônjuge
4. {surnames_info} — entradas com esses sobrenomes marcar como "revisao"
5. Entradas com mesmo nome do titular (self-transfer) — DESCONSIDERAR
6. Transferências de CNPJ são renda válida (pró-labore, salário)
7. Calcule renda apurada por mês = soma das entradas "valida"
8. Média = soma dos meses ÷ número de meses (divisão exata)
9. Separe corretamente os meses mesmo que o extrato cubra múltiplos meses

Titular: {clientName or "Não informado"}

Responda APENAS com JSON puro (sem markdown, sem texto antes ou depois):
{{
  "titular": "nome completo como no extrato",
  "banco": "nome do banco",
  "periodo": "Ex: Janeiro a Março de 2026",
  "meses": [
    {{
      "mes": "Janeiro 2026",
      "totalBruto": 0.00,
      "rendaApurada": 0.00,
      "entradas": [
        {{ "data": "DD/MM", "descricao": "texto completo", "valor": 0.00, "status": "valida|desconsiderada|revisao", "motivo": "breve justificativa" }}
      ]
    }}
  ],
  "media": 0.00,
  "itensRevisao": [
    {{ "data": "DD/MM", "mes": "Mês Ano", "nome": "Nome Remetente", "valor": 0.00, "observacao": "texto" }}
  ],
  "observacoes": "perfil de renda e observações relevantes"
}}"""
        })

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": content}]
        )

        text = response.content[0].text
        # Extrair JSON
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if not match:
            return JSONResponse(status_code=500, content={"error": "IA não retornou JSON válido"})

        import json
        result = json.loads(match.group(0))
        return JSONResponse(content=result)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
