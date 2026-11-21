# predictor.py
import json
import ollama
import pandas as pd
from config import TESTING_MODE

class OllamaForexPredictor:
    def __init__(self, model_name="martain7r/finance-llama-8b:q4_k_m"):
        self.model_name = model_name
        self.client = ollama.Client()

    def predict_next_pips(self, pips_series: pd.Series, rsi_value: float, dist_ema: float, atr_pips: float):
        """
        Calcula la inferència mitjançant Ollama avaluant tant BUY com SELL de forma equilibrada.
        """
        num_candles = 8 if TESTING_MODE else 15
        recent_pips = [round(x, 2) for x in pips_series.tail(num_candles).tolist()]
        trend_hint = "BULLISH (favor BUY or HOLD)" if dist_ema >= 0 else "BEARISH (favor SELL or HOLD)"

        if TESTING_MODE:
            prompt = f"""Reply ONLY with valid JSON (no markdown). Evaluate BOTH BUY and SELL equally.
Inputs: Pips={recent_pips}, RSI={rsi_value:.1f}, DistEMA={dist_ema:.1f} ({trend_hint}), ATR={atr_pips:.1f}.
Rules: Assign confidence >= 85 ONLY for clear momentum aligned with DistEMA (BUY if DistEMA > 0, SELL if DistEMA < 0). Otherwise use HOLD with confidence < 50.
Schema:
{{"confidence": <0-100>, "direction": "<BUY/SELL/HOLD>", "suggested_tp_pips": <num>, "suggested_sl_pips": <num>, "reasoning": "fast"}}"""

            ollama_options = {
                "num_predict": 90,
                "temperature": 0.0,
                "seed": 42,
                "top_k": 1
            }
        else:
            prompt = f"""
System: You are an extremely conservative risk-management trading AI. Your primary directive is CAPITAL PRESERVATION.
Analyze the input data and reply ONLY with a valid JSON object. Evaluate BOTH long (BUY) and short (SELL) opportunities equally.

Input Data:
- Recent Candles (Pips Change): 
{recent_pips}
- Current RSI (14): 
{rsi_value:.1f}
- Distance to EMA200 (Pips): 
{dist_ema:.1f} -> Trend Context: {trend_hint}
- Current Volatility / ATR(14) in Pips: 
{atr_pips:.1f}

Strict Scoring Rules:
- Be EXTREMELY conservative. Assign confidence >= 85 ONLY when momentum and RSI strongly confirm the EMA200 trend (BUY only if DistEMA > 0; SELL only if DistEMA < 0).
- If the market is sideways, choppy, or lacks strong momentum, output confidence < 50 and direction "HOLD".
- Do NOT guess. When in doubt, always default to "HOLD".

Respond EXCLUSIVELY with this JSON schema:
{{
    "confidence": <number 0-100 representing certainty in the chosen direction>,
    "direction": "<BUY, SELL or HOLD>",
    "suggested_tp_pips": <number based on ATR>,
    "suggested_sl_pips": <number based on ATR>,
    "reasoning": "<short sentence in English>"
}}
"""
            ollama_options = {
                "num_predict": 130,
                "temperature": 0.0,
                "seed": 42,
                "top_k": 1
            }

        try:
            response = self.client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options=ollama_options
            )

            content = response['message']['content'].strip()

            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                if not content.endswith("}"):
                    content_reparado = content + '"}' if not content.endswith('"') else content + "}"
                    data = json.loads(content_reparado)
                else:
                    raise

            prob = float(data.get("confidence", data.get("probability_up", 0.0)))
            direction = str(data.get("direction", "HOLD")).upper().strip()
            reasoning = data.get("reasoning", "No details")

            tp_ia = float(data.get("suggested_tp_pips", atr_pips * 2.0))
            sl_ia = float(data.get("suggested_sl_pips", atr_pips * 1.0))

            return {
                "probabilidad": prob,
                "direccion": direction,
                "razonamiento": reasoning,
                "suggested_tp": max(tp_ia, 15.0),
                "suggested_sl": max(sl_ia, 10.0)
            }

        except Exception:
            return {
                "probabilidad": 0.0,
                "direccion": "HOLD",
                "razonamiento": "JSON Error fallback",
                "suggested_tp": 20.0,
                "suggested_sl": 10.0
            }