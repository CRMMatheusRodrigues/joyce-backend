from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import google.generativeai as genai
import os
import re
import json
from typing import List

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

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
        surnames_info = f"Sobrenomes familiares para DESCONSIDERAR: {familyNames}" if familyNames else "Nenhum sobrenome familiar informado."

        prompt = f"""Você é especialista em apuração de renda para fins imobiliários no Brasil.

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

        model = genai.GenerativeModel("gemini-2.0-flash")

        parts = []
        for arquivo in arquivos:
            dados = await arquivo.read()
            parts.append({
                "inline_data": {
                    "mime_type": "application/pdf",
                    "data": dados
                }
            })
        parts.append(prompt)

        response = model.generate_content(parts)
        text = response.text

        match = re.search(r'\{[\s\S]*\}', text)
        if not match:
            return JSONResponse(status_code=500, content={"error": "IA não retornou JSON válido"})

        result = json.loads(match.group(0))
        return JSONResponse(content=result)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
