# 📘 README — Auditoria Visual Multi-Contas da Folha

Este notebook implementa uma **auditoria visual de contas contábeis da folha de pagamento**, baseada em boas práticas de BPOs como ADP e padrões internacionais (CBA).  
A proposta é identificar **variações críticas** (possíveis erros ou inconsistências) através de gráficos interativos.  

---

## 🚀 Objetivo
- Visualizar as **principais contas contábeis da folha** (salários, encargos, benefícios, férias, 13º etc.).  
- Marcar automaticamente **pontos de atenção**:  
  - **Baixo** → valor mínimo inesperado.  
  - **Alto** → valor máximo após esse ponto (pico).  
- Permitir ao auditor **ativar/desativar contas** pela legenda (usando **Ctrl+Click**).  

---

## 📂 Estrutura dos Dados
O CSV deve conter colunas no formato:

| Mes       | Headcount | Folha_Bruta | Horas_Extras | Beneficios | INSS | FGTS | Ferias | 13o | Rescisoes | PLR |
|-----------|-----------|-------------|--------------|------------|------|------|--------|-----|-----------|-----|
| 2023-01-31| 120       | 580000      | 32000        | 85000      | 116000| 46000| 22000  | 0   | 18000     | 0   |

- **Mes**: data de referência (mês/ano).  
- **Headcount**: número de funcionários ativos.  
- **Folha_Bruta**: salários brutos do mês.  
- **Horas_Extras**: adicionais de jornada.  
- **Beneficios**: total de benefícios.  
- **INSS**: contribuição previdenciária patronal.  
- **FGTS**: depósitos de FGTS.  
- **Ferias**: pagamentos de férias.  
- **13o**: parcelas de 13º salário.  
- **Rescisoes**: desligamentos.  
- **PLR**: participação nos lucros/resultados.  

---

## 🧩 Explicação do Código

### 1. Carregar e preparar os dados
```python
df = pd.read_csv("folha_simulada_completa.csv", sep=";")
df["Mes"] = pd.to_datetime(df["Mes"])
```
- Lê o CSV.  
- Converte a coluna `Mes` em formato de data para o eixo do tempo.  

### 2. Definir as contas e cores
```python
contas = ["Folha_Bruta", "Horas_Extras", "Beneficios", "INSS", "FGTS", "Ferias", "13o", "Rescisoes", "PLR"]
```
- Lista de contas relevantes.  
- Paleta de cores baseada em **Bootstrap** para fácil leitura.  

### 3. Criar linhas e issues
Cada conta é desenhada como linha **+ issues (baixo/alto)**.  
`legendonly`: aparece na legenda, mas não no gráfico inicial.  

### 4. Layout e exibição
Define título, estilo visual, legenda e slider no eixo X.  

---

## 📊 Como usar
1. Execute a célula.  
2. O gráfico abrirá **em branco**.  
3. Use a **legenda** → clique em `Folha_Bruta`, `INSS` etc. para ativar.  
4. Use **Ctrl+Click** para ativar múltiplas contas.  
5. Marcas de **“Baixo”** e **“Alto”** aparecerão automaticamente para destacar outliers.  

---

## ✅ Benefícios do modelo
- Evita **poluição visual** (abre vazio).  
- Cada conta tem **cor única + issues marcados**.  
- Permite **análises cruzadas** (ex.: Folha x INSS x FGTS).  
- Funciona como uma auditoria visual (Gross Verify & Possible Issues).  
