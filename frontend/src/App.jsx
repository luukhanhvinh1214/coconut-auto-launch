import { useEffect, useRef, useState } from 'react'
import logo from './logo.png'

// window.pywebview.api là object rỗng cho tới khi sự kiện pywebviewready chạy.
function whenApiReady() {
  return new Promise((resolve) => {
    if (window.pywebview?.api?.get_state) resolve(window.pywebview.api)
    else window.addEventListener('pywebviewready', () => resolve(window.pywebview.api), { once: true })
  })
}

const describe = (action, err) => `${action}: ${err?.message ?? err}`

// Bỏ dấu để gõ "khanh" vẫn tìm ra "Khánh".
const fold = (text) =>
  text
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/đ/g, 'd')

function Picker({ api, onPick, onClose }) {
  const dialog = useRef(null)
  const [catalog, setCatalog] = useState(null)
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!dialog.current.open) dialog.current.showModal()
    api.list_apps().then(setCatalog, (err) => setError(describe('Không đọc được danh sách ứng dụng', err)))
  }, [api])

  const words = fold(query).split(/\s+/).filter(Boolean)
  const results = (catalog ?? []).filter((app) => {
    const text = fold(`${app.name} ${app.detail}`)
    return words.every((word) => text.includes(word))
  })

  const onKeyDown = (event) => {
    if (event.key === 'Enter' && results.length > 0) onPick(results[0])
  }

  const browse = () =>
    api
      .pick_app()
      .then((app) => app && onPick(app))
      .catch((err) => setError(describe('Không mở được hộp chọn tệp', err)))

  return (
    <dialog ref={dialog} className="picker" onClose={onClose} aria-labelledby="picker-title">
      <h2 id="picker-title">Thêm ứng dụng</h2>
      <input
        className="field search"
        type="search"
        placeholder="Tìm ứng dụng"
        aria-label="Tìm ứng dụng"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={onKeyDown}
        autoFocus
      />

      <div className="picker-body">
        {catalog === null && !error && <p className="empty">Đang tải...</p>}
        {catalog !== null && results.length === 0 && <p className="empty">Không tìm thấy ứng dụng.</p>}
        {results.length > 0 && (
          <ul className="tiles">
            {results.map((app, i) => (
              <li key={app.path + app.args}>
                <button
                  type="button"
                  className={i === 0 && words.length > 0 ? 'tile first' : 'tile'}
                  onClick={() => onPick(app)}
                >
                  <span className="tile-name">{app.name}</span>
                  {app.detail && <span className="tile-detail">{app.detail}</span>}
                </button>
              </li>
            ))}
          </ul>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </div>

      <div className="picker-foot">
        <button type="button" className="secondary" onClick={browse}>
          Chọn tệp khác
        </button>
        <button type="button" className="secondary" onClick={() => dialog.current.close()}>
          Đóng
        </button>
      </div>
    </dialog>
  )
}

export default function App() {
  const [api, setApi] = useState(null)
  const [apps, setApps] = useState(null)
  const [startup, setStartup] = useState(false)
  const [picking, setPicking] = useState(false)
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

  const add = (app) => {
    setPicking(false)
    update([...apps, { name: app.name, path: app.path, args: app.args, fullscreen: false }])
  }

  const toggleStartup = (event) =>
    api
      .set_startup(event.target.checked)
      .then(setStartup)
      .catch((err) => setError(describe('Không đổi được chế độ khởi động', err)))

  const ready = apps !== null

  return (
    <div className="shell">
      <header className="husk">
        <div className="brand">
          <img className="logo" src={logo} alt="" />
          <h1>Coconut Auto Launch</h1>
        </div>
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
            <button type="button" className="primary" onClick={() => setPicking(true)} disabled={!ready}>
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
                <col className="col-full" />
                <col className="col-action" />
              </colgroup>
              <thead>
                <tr>
                  <th>Tên</th>
                  <th>Đường dẫn</th>
                  <th className="center">FullScreen</th>
                  <th>
                    <span className="sr-only">Xoá</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {apps.map((app, i) => {
                  const target = app.args ? `${app.path} ${app.args}` : app.path
                  return (
                    <tr key={i}>
                      <td>
                        <input
                          className="field"
                          value={app.name}
                          onChange={(e) => edit(i, 'name', e.target.value)}
                          aria-label={`Tên ứng dụng ${i + 1}`}
                        />
                      </td>
                      <td className="path" title={target}>
                        {target}
                      </td>
                      <td className="center">
                        <input
                          className="check"
                          type="checkbox"
                          checked={app.fullscreen}
                          onChange={(e) => edit(i, 'fullscreen', e.target.checked)}
                          aria-label={`FullScreen cho ${app.name || 'ứng dụng ' + (i + 1)}`}
                        />
                      </td>
                      <td>
                        <button type="button" className="remove" onClick={() => remove(i)}>
                          Xoá
                        </button>
                      </td>
                    </tr>
                  )
                })}
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

      <footer className="sign">
        <span>(+84) 898 447 154 | luukhanhvinh1214@gmail.com</span>
        <span>2026 Lưu Khánh Vinh</span>
      </footer>

      {picking && <Picker api={api} onPick={add} onClose={() => setPicking(false)} />}
    </div>
  )
}
