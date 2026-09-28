"""Diagnose a Freqtrade backtest: exit reasons, win/loss sizes, give-back from the best price (MFE)."""
import sys
from pathlib import Path
from freqtrade.data.btanalysis import load_backtest_data, load_backtest_stats
res = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted(Path('user_data/backtest_results').glob('*.meta.json'))[-1]
res = Path(str(res).replace('.meta.json', '.zip'))
df = load_backtest_data(res)
st = load_backtest_stats(res)
s = st['strategy'][list(st['strategy'])[0]]
print(f"file {res.name}: trades {len(df)} | profit {s['profit_total']*100:.1f}% | maxDD {s['max_drawdown_account']*100:.1f}% | winrate {s['winrate']*100:.0f}% | PF {s.get('profit_factor',0):.2f}")
df['mfe'] = (df['max_rate'] - df['open_rate']) / df['open_rate']
df['mae'] = (df['min_rate'] - df['open_rate']) / df['open_rate']
df['giveback'] = df['mfe'] - df['profit_ratio']
w, l = df[df.profit_abs > 0], df[df.profit_abs <= 0]
print(f"avg win {w.profit_ratio.mean()*100:.2f}% | avg loss {l.profit_ratio.mean()*100:.2f}% | payoff {w.profit_ratio.mean()/abs(l.profit_ratio.mean()):.2f}")
print(f"avg best run (MFE) all {df.mfe.mean()*100:.2f}% | winners {w.mfe.mean()*100:.2f}% | losers {l.mfe.mean()*100:.2f}%")
print(f"losers that were once >+2%: {(l.mfe>0.02).mean()*100:.0f}% | >+3%: {(l.mfe>0.03).mean()*100:.0f}%  (profits given back)")
print(f"avg give-back from best price: {df.giveback.mean()*100:.2f}% | median duration {df.trade_duration.median():.0f} min")
print("exit reasons:")
g = df.groupby('exit_reason').agg(n=('profit_abs','size'), pnl=('profit_abs','sum'), avg=('profit_ratio','mean'), win=('profit_abs', lambda x: (x>0).mean()))
print(g.sort_values('n', ascending=False).round(3).to_string())
