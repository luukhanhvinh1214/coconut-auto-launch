import { useEffect, useRef, useState } from 'react'

// window.pywebview.api là object rỗng cho tới khi sự kiện pywebviewready chạy.
function whenApiReady() {
  return new Promise((resolve) => {
    if (window.pywebview?.api?.get_state) resolve(window.pywebview.api)
    else window.addEventListener('pywebviewready', () => resolve(window.pywebview.api), { once: true })
  })
}

const describe = (action, err) => `${action}: ${err?.message ?? err}`

const toDelay = (value) => (value === '' ? '' : Math.max(0, Math.floor(Number(value))))

export default function App() {
  const [api, setApi] = useState(null)
  const [apps, setApps] = useState(null)
  const [startup, setStartup] = useState(false)
  const [error, setError] = useState('')
  const saving = useRef(Promise.resolve())

  useEffect(() => {
    whenApiReady()
      .then(async (ready) => {
        const state = await ready.get_state()
        setApi(ready)
        setApps(state.apps)
        setStartup(state.startup)
      })
      .catch((err) => setError(describe('Không đọc được danh sách', err)))
  }, [])

  const update = (next) => {
    setApps(next)
    // Mỗi lời gọi Python chạy trên thread riêng, xếp hàng để bản mới nhất được ghi sau cùng.
    saving.current = saving.current
      .then(() => api.save_apps(next))
      .then(() => setError(''), (err) => setError(describe('Không lưu được danh sách', err)))
  }

  const edit = (index, field, value) =>
    update(apps.map((app, i) => (i === index ? { ...app, [field]: value } : app)))

  const remove = (index) => update(apps.filter((_, i) => i !== index))

  const add = () =>
    api
      .pick_app()
      .then((app) => app && update([...apps, app]))
      .catch((err) => setError(describe('Không thêm được ứng dụng', err)))

  const toggleStartup = (event) =>
    api
      .set_startup(event.target.checked)
      .then(setStartup)
      .catch((err) => setError(describe('Không đổi được chế độ khởi động', err)))

  const ready = apps !== null

  return (
    <div className="shell">
      <header className="husk">
        <h1>Coconut Auto Launch</h1>
        <label className="switch">
          <span>Khởi động cùng Windows</span>
          <input type="checkbox" role="switch" checked={startup} onChange={toggleStartup} disabled={!ready} />
          <span className="track" aria-hidden="true" />
          <span className="switch-state">{startup ? 'Bật' : 'Tắt'}</span>
        </label>
      </header>

      <main className="water">
        <section className="flesh">
          <div className="flesh-head">
            <h2>Danh sách ứng dụng</h2>
            <button type="button" className="primary" onClick={add} disabled={!ready}>
              Thêm ứng dụng
            </button>
          </div>

          {!ready && !error && <p className="empty">Đang tải...</p>}
          {ready && apps.length === 0 && <p className="empty">Chưa có ứng dụng nào.</p>}
          {ready && apps.length > 0 && (
            <table>
              <colgroup>
                <col className="col-name" />
                <col />
                <col className="col-delay" />
                <col className="col-action" />
              </colgroup>
              <thead>
                <tr>
                  <th>Tên</th>
                  <th>Đường dẫn</th>
                  <th>Độ trễ (giây)</th>
                  <th>
                    <span className="sr-only">Xoá</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {apps.map((app, i) => (
                  <tr key={i}>
                    <td>
                      <input
                        className="field"
                        value={app.name}
                        onChange={(e) => edit(i, 'name', e.target.value)}
                        aria-label={`Tên ứng dụng ${i + 1}`}
                      />
                    </td>
                    <td className="path" title={app.path}>
                      {app.path}
                    </td>
                    <td>
                      <input
                        className="field"
                        type="number"
                        min="0"
                        step="1"
                        value={app.delay}
                        onChange={(e) => edit(i, 'delay', toDelay(e.target.value))}
                        aria-label={`Độ trễ của ${app.name || 'ứng dụng ' + (i + 1)}`}
                      />
                    </td>
                    <td>
                      <button type="button" className="remove" onClick={() => remove(i)}>
                        Xoá
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </main>
    </div>
  )
}
