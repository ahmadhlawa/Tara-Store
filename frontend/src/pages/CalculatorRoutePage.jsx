import { useState } from "react";

// Resin volume helper kept from the original storefront: a purely local tool,
// no API and no product data involved.
export default function CalculatorRoutePage() {
  const [calc, setCalc] = useState({ shape: "round", dia: 20, side: 20, height: 2, layers: 1 });
  const update = (patch) => setCalc((current) => ({ ...current, ...patch }));

  const volume =
    (calc.shape === "round" ? Math.PI * (Number(calc.dia) / 2) ** 2 : Number(calc.side) ** 2) *
    Number(calc.height) *
    Number(calc.layers || 1);
  const grams = volume * 1.1 * 1.1;

  return (
    <section className="vs-container vs-container--narrow vs-section">
      <h1 className="vs-page__title">حاسبة نسب المواد</h1>
      <p className="vs-page__lead">
        قدّر كمية الريزن اللازمة لقالبك. النتيجة تقريبية وتعتمد على كثافة المادة المستخدمة.
      </p>

      <div className="vs-calc">
        <div className="vs-calc__form">
          <div className="vs-calc__shapes" role="group" aria-label="شكل القالب">
            <button
              type="button"
              className="vs-chip"
              aria-pressed={calc.shape === "round"}
              onClick={() => update({ shape: "round" })}
            >
              دائري
            </button>
            <button
              type="button"
              className="vs-chip"
              aria-pressed={calc.shape === "square"}
              onClick={() => update({ shape: "square" })}
            >
              مربّع
            </button>
          </div>

          {calc.shape === "round" ? (
            <label className="vs-field">
              القطر (سم)
              <input
                className="vs-input"
                type="number"
                min="1"
                value={calc.dia}
                onChange={(event) => update({ dia: event.target.value })}
              />
            </label>
          ) : (
            <label className="vs-field">
              طول الضلع (سم)
              <input
                className="vs-input"
                type="number"
                min="1"
                value={calc.side}
                onChange={(event) => update({ side: event.target.value })}
              />
            </label>
          )}

          <label className="vs-field">
            الارتفاع (سم)
            <input
              className="vs-input"
              type="number"
              min="0.1"
              step="0.1"
              value={calc.height}
              onChange={(event) => update({ height: event.target.value })}
            />
          </label>

          <label className="vs-field">
            عدد الطبقات
            <input
              className="vs-input"
              type="number"
              min="1"
              value={calc.layers}
              onChange={(event) => update({ layers: event.target.value })}
            />
          </label>
        </div>

        <aside className="vs-calc__result" aria-live="polite">
          <span className="vs-calc__label">الكمية الإجمالية التقريبية</span>
          <strong className="vs-calc__total">{grams > 0 ? Math.round(grams) : 0} غم</strong>
          <dl className="vs-specs">
            <div className="vs-specs__row">
              <dt>الريزن (٢:١)</dt>
              <dd>{Math.round((grams * 2) / 3)} غم</dd>
            </div>
            <div className="vs-specs__row">
              <dt>المصلّب</dt>
              <dd>{Math.round(grams / 3)} غم</dd>
            </div>
            <div className="vs-specs__row">
              <dt>الحجم</dt>
              <dd>{Math.round(volume)} سم³</dd>
            </div>
          </dl>
        </aside>
      </div>
    </section>
  );
}
