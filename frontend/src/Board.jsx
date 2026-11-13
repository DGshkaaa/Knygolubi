import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { boardApi } from './api'
import { useAuth } from './auth'
import './board.css'

const kinds = {
  wanted: { label: 'Шукаю книгу', icon: '⌕', hint: 'Потрібна книга, якої немає на полиці? Запитайте спільноту.' },
  exchange: { label: 'Обміняю', icon: '⇄', hint: 'Розкажіть, яку книгу маєте та що хотіли б прочитати натомість.' },
  giveaway: { label: 'Подарую', icon: '♡', hint: 'Дайте прочитаній книзі шанс на нову історію.' },
}
const canWrite = (user) => Boolean(user && (['admin', 'moderator'].includes(user.role) || (user.email_verified && user.is_approved)))
const date = (value) => new Date(value).toLocaleDateString('uk-UA', { day: 'numeric', month: 'long', timeZone: 'Europe/Kyiv' })
const errorText = (error) => typeof error.response?.data?.detail === 'string' ? error.response.data.detail : 'Не вдалося виконати дію. Перевірте з’єднання та спробуйте ще раз.'
const emptyPost = { kind: 'wanted', book_title: '', book_author: '', description: '', location: '' }

export function BoardTabs({ active = 'board' }) {
  return <div className="catalog-tabs board-tabs" aria-label="Розділи бібліотеки">
    <Link to="/" className={active === 'catalog' ? 'active' : ''}><span aria-hidden="true">▦</span>Каталог</Link>
    <Link to="/board" className={active === 'board' ? 'active' : ''}><span aria-hidden="true">⇄</span>Дошка спільноти</Link>
  </div>
}

function AccessNote() {
  const { user, isAuthenticated } = useAuth()
  if (canWrite(user)) return null
  return <div className="board-access">{isAuthenticated
    ? 'Переглядати оголошення можна вже зараз. Для публікації та відгуків підтвердіть пошту й дочекайтеся схвалення модератора.'
    : <>Знаходьте книги разом зі спільнотою. <Link to="/login">Увійдіть</Link>, щоб публікувати оголошення та писати читачам.</>}</div>
}

function PostCard({ post }) {
  const kind = kinds[post.kind]
  return <Link className={`board-post board-${post.kind}`} to={`/board/${post._id}`}>
    <div className="board-post-top"><span className="board-kind"><span aria-hidden="true">{kind.icon}</span>{kind.label}</span>{post.status !== 'open' && <span className="board-status">{post.status === 'closed' ? 'Закрито' : 'Строк минув'}</span>}</div>
    <h2>{post.book_title}</h2>
    <p className="board-book-author">{post.book_author || 'Автор не вказаний'}</p>
    <p className="board-excerpt">{post.description}</p>
    {post.location && <p className="board-location">⌖ {post.location}</p>}
    <div className="board-card-footer"><span><b>{post.owner_name.slice(0, 1)}</b>{post.owner_name}</span><time dateTime={post.created_at}>{date(post.created_at)}</time></div>
    <span className="board-card-link">Переглянути оголошення <span aria-hidden="true">↗</span></span>
  </Link>
}

export function BoardPage() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const mine = params.get('scope') === 'mine'
  const [search, setSearch] = useState('')
  const [kind, setKind] = useState('')
  const [page, setPage] = useState(1)
  const [result, setResult] = useState({ posts: [], total: 0, hasNext: false, loading: true, error: '' })
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    if (mine && !canWrite(user)) return
    let active = true
    const timer = setTimeout(() => {
      setResult(current => ({ ...current, loading: true, error: '' }))
      const query = { search: search.trim() || undefined, kind: kind || undefined, page, page_size: 9 }
      ;(mine ? boardApi.mine(query) : boardApi.list(query)).then(({ data, headers }) => {
        if (active) setResult({ posts: data, total: Number(headers['x-total-count'] || 0), hasNext: headers['x-has-next'] === 'true', loading: false, error: '' })
      }).catch(error => { if (active) setResult({ posts: [], total: 0, hasNext: false, loading: false, error: errorText(error) }) })
    }, 250)
    return () => { active = false; clearTimeout(timer) }
  }, [mine, user, search, kind, page, revision])
  const filter = (setter, value) => { setter(value); setPage(1) }
  return <section className="page board-page">
    <BoardTabs />
    <div className="board-hero">
      <div><p className="eyebrow">ВІД ЧИТАЧА ДО ЧИТАЧА</p><h1>Книги знаходять<br />своїх людей.</h1><p>Шукайте потрібне, обмінюйте прочитане й даруйте історіям новий дім.</p>{canWrite(user) && <Link className="primary" to="/board/new">＋ Створити оголошення</Link>}</div>
      <div className="board-hero-art" aria-hidden="true"><span>Вже прочитав?</span><strong>Передай<br />історію далі.</strong><i>BOOKWAY COMMUNITY ↗</i></div>
    </div>
    <div className="board-how"><span><b>01</b>Розкажіть про книгу</span><span><b>02</b>Отримайте приватний відгук</span><span><b>03</b>Домовтеся та закрийте оголошення</span></div>
    <AccessNote />
    <div className="board-toolbar">
      <div className="board-scope" aria-label="Оголошення"><button className={!mine ? 'active' : ''} onClick={() => { setParams({}); setPage(1) }}>Усі оголошення</button>{canWrite(user) && <button className={mine ? 'active' : ''} onClick={() => { setParams({ scope: 'mine' }); setPage(1) }}>Мої оголошення</button>}</div>
      <label className="board-search"><span className="sr-only">Пошук оголошень</span><span aria-hidden="true">⌕</span><input type="search" placeholder="Книга, автор або слова з опису…" value={search} onChange={event => filter(setSearch, event.target.value)} />{search && <button aria-label="Очистити пошук" onClick={() => filter(setSearch, '')}>×</button>}</label>
    </div>
    <div className="board-kind-filters" aria-label="Тип оголошення">{[['', 'Усі'], ...Object.entries(kinds).map(([key, value]) => [key, `${value.icon} ${value.label}`])].map(([key, label]) => <button key={key} aria-pressed={kind === key} className={kind === key ? 'active' : ''} onClick={() => filter(setKind, key)}>{label}</button>)}</div>
    {mine && !canWrite(user) ? <div className="board-empty"><h2>Ваші оголошення будуть тут</h2><p>Увійдіть зі схваленим профілем, щоб керувати публікаціями.</p><Link className="secondary" to="/login">Увійти</Link></div> : result.loading ? <p className="board-empty" role="status">Завантажуємо оголошення…</p> : result.error ? <div className="board-empty" role="alert"><p>{result.error}</p><button className="secondary" onClick={() => setRevision(value => value + 1)}>Спробувати ще раз</button></div> : <>
      <p className="board-result-count" role="status">{mine ? 'Ваші публікації' : 'Актуальні оголошення'} · {result.total}</p>
      {result.posts.length ? <div className="board-grid">{result.posts.map(post => <PostCard key={post._id} post={post} />)}</div> : <div className="board-empty"><span aria-hidden="true">⇄</span><h2>{search || kind ? 'Поки немає збігів' : mine ? 'Почніть свою історію' : 'Будьте першими на дошці'}</h2><p>{search || kind ? 'Спробуйте інші слова або виберіть усі типи оголошень.' : 'Є книга, яку давно шукаєте? Або та, якою готові поділитися? Напишіть про неї.'}</p>{canWrite(user) && <Link className="primary" to="/board/new">Створити оголошення</Link>}</div>}
      {(page > 1 || result.hasNext) && <div className="pagination"><button className="secondary" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Попередня</button><span>Сторінка {page}</span><button className="secondary" disabled={!result.hasNext} onClick={() => setPage(value => value + 1)}>Наступна</button></div>}
    </>}
  </section>
}

export function BoardEditor() {
  const { postId } = useParams()
  return <BoardEditorContent key={postId || 'new'} postId={postId} />
}

function BoardEditorContent({ postId }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState(emptyPost)
  const [loading, setLoading] = useState(Boolean(postId))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [editable, setEditable] = useState(!postId)
  useEffect(() => {
    if (!postId) return
    let active = true
    boardApi.get(postId).then(({ data }) => {
      if (!active) return
      if (data.owner_id !== user?._id) { setError('Редагувати оголошення може лише його автор.'); return }
      setForm(Object.fromEntries(Object.keys(emptyPost).map(key => [key, data[key]])))
      setEditable(true)
    }).catch(error => { if (active) setError(errorText(error)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [postId, user?._id])
  const change = (key, value) => setForm(current => ({ ...current, [key]: value }))
  const submit = async event => {
    event.preventDefault()
    if (busy) return
    setBusy(true); setError('')
    try {
      const { data } = await (postId ? boardApi.update(postId, form) : boardApi.create(form))
      navigate(`/board/${data._id}`)
    } catch (error) { setError(errorText(error)) } finally { setBusy(false) }
  }
  return <section className="page board-editor"><Link className="board-back" to={postId ? `/board/${postId}` : '/board'}>← До {postId ? 'оголошення' : 'дошки'}</Link><p className="eyebrow">ВАША КНИГА · ВАША ІСТОРІЯ</p><h1>{postId ? 'Редагувати оголошення' : 'Знайдіть свого читача'}</h1><AccessNote />{loading ? <p role="status">Завантаження…</p> : canWrite(user) && editable && <form className="board-form" onSubmit={submit}>
    <fieldset disabled={busy}><legend>Що ви хочете зробити?</legend><div className="board-kind-choice">{Object.entries(kinds).map(([key, value]) => <label key={key} className={form.kind === key ? 'active' : ''}><input type="radio" name="kind" value={key} checked={form.kind === key} onChange={() => change('kind', key)} /><span aria-hidden="true">{value.icon}</span>{value.label}</label>)}</div><p className="field-hint">{kinds[form.kind].hint}</p>
      <label>Назва книги<input required maxLength={200} value={form.book_title} placeholder="Наприклад, «Місто»" onChange={event => change('book_title', event.target.value)} /></label>
      <label>Автор <small>необов’язково</small><input maxLength={160} value={form.book_author} placeholder="Валер’ян Підмогильний" onChange={event => change('book_author', event.target.value)} /></label>
      <label>Подробиці<textarea required minLength={10} maxLength={2000} rows={5} value={form.description} placeholder="Стан книги, бажане видання або на що готові обміняти. Без особистих контактів — для них є приватна розмова." onChange={event => change('description', event.target.value)} /><small>{form.description.length}/2000 символів</small></label>
      <label>Місто або місце обміну <small>необов’язково</small><input maxLength={120} value={form.location} placeholder="Наприклад, Київ або бібліотека коледжу" onChange={event => change('location', event.target.value)} /></label>
      <div className="board-form-note">Оголошення активне 30 днів. Коли домовитеся, позначте його як завершене. Книги з дошки не додаються автоматично до бібліотечного каталогу.</div>
      <button className="primary" type="submit">{busy ? 'Зберігаємо…' : postId ? 'Зберегти зміни' : 'Опублікувати оголошення'}</button>
    </fieldset>
  </form>}{error && <p className="auth-feedback error" role="alert">{error}</p>}</section>
}

function Conversation({ thread, ownerName, currentUserId, onUpdated }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const send = async event => {
    event.preventDefault()
    if (busy || !text.trim()) return
    setBusy(true); setError('')
    try { const { data } = await boardApi.message(thread._id, text); setText(''); onUpdated(data) }
    catch (error) { setError(errorText(error)) } finally { setBusy(false) }
  }
  return <article className="board-conversation"><div className="board-conversation-heading"><strong>Розмова з <Link to={`/users/${currentUserId === thread.owner_id ? thread.responder_id : thread.owner_id}`}>{currentUserId === thread.owner_id ? thread.responder_name : ownerName} ↗</Link></strong><span>Приватно · {thread.messages.length}/50</span></div><div className="board-messages">{thread.messages.map((message, index) => <div className={`board-message ${message.sender_id === currentUserId ? 'own' : ''}`} key={`${message.created_at}-${index}`}><span>{message.sender_id === currentUserId ? 'Ви' : message.sender_id === thread.owner_id ? ownerName : thread.responder_name}</span><p>{message.text}</p><time>{new Date(message.created_at).toLocaleString('uk-UA', { timeZone: 'Europe/Kyiv', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</time></div>)}</div>{thread.messages.length < 50 && <form onSubmit={send} className="board-message-form"><label><span className="sr-only">Повідомлення для {currentUserId === thread.owner_id ? thread.responder_name : ownerName}</span><textarea required maxLength={1000} rows={2} placeholder="Домовтеся про обмін або передачу книги…" value={text} disabled={busy} onChange={event => setText(event.target.value)} /></label><button className="primary" disabled={busy || !text.trim()}>{busy ? 'Надсилаємо…' : 'Надіслати'}</button></form>}{error && <p role="alert" className="error">{error}</p>}</article>
}

export function BoardDetail() {
  const { postId } = useParams()
  return <BoardDetailContent key={postId} postId={postId} />
}

function BoardDetailContent({ postId }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [post, setPost] = useState(null)
  const [threads, setThreads] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [replyError, setReplyError] = useState('')
  const [busy, setBusy] = useState(false)
  const [text, setText] = useState('')
  const [revision, setRevision] = useState(0)
  const [responseLoading, setResponseLoading] = useState(true)
  const owner = post && user?._id === post.owner_id
  const staff = user && ['admin', 'moderator'].includes(user.role)
  const allowed = canWrite(user)
  const refresh = useCallback(() => setRevision(value => value + 1), [])
  useEffect(() => {
    let active = true
    boardApi.get(postId).then(({ data }) => { if (active) { setPost(data); setError('') } }).catch(error => { if (active) setError(errorText(error)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [postId, revision])
  useEffect(() => {
    if (!allowed) return
    let active = true
    const load = () => boardApi.responses(postId).then(({ data }) => { if (active) { setThreads(data); setReplyError('') } }).catch(error => { if (active) setReplyError(errorText(error)) }).finally(() => { if (active) setResponseLoading(false) })
    load()
    const timer = setInterval(() => { if (!document.hidden) load() }, 20000)
    return () => { active = false; clearInterval(timer) }
  }, [postId, allowed, user?._id, revision])
  const action = async type => {
    if (busy) return
    if (type === 'delete' && !window.confirm('Видалити оголошення разом із його розмовами?')) return
    setBusy(true); setError('')
    try {
      if (type === 'delete') { await boardApi.remove(postId); navigate('/board'); return }
      const { data } = await boardApi.status(postId, post.status === 'open' ? 'closed' : 'open'); setPost(data)
    } catch (error) { setError(errorText(error)) } finally { setBusy(false) }
  }
  const respond = async event => {
    event.preventDefault()
    if (busy || !text.trim()) return
    setBusy(true); setReplyError('')
    try { const { data } = await boardApi.respond(postId, text); setThreads([data]); setText('') }
    catch (error) { setReplyError(errorText(error)); refresh() } finally { setBusy(false) }
  }
  const updateThread = data => setThreads(current => current.map(thread => thread._id === data._id ? data : thread))
  if (loading) return <section className="page board-detail" role="status">Завантажуємо оголошення…</section>
  if (!post) return <section className="page board-detail"><Link to="/board">← До дошки</Link><p className="auth-feedback error" role="alert">{error || 'Оголошення не знайдено.'}</p><button className="secondary" onClick={refresh}>Спробувати ще раз</button></section>
  return <section className="page board-detail"><Link className="board-back" to="/board">← Усі оголошення</Link><article className={`board-detail-card board-${post.kind}`}><span className="board-kind">{kinds[post.kind].icon} {kinds[post.kind].label}</span><h1>{post.book_title}</h1>{post.book_author && <p className="author">{post.book_author}</p>}<div className="board-detail-meta"><Link to={`/users/${post.owner_id}`}>{post.owner_name} ↗</Link><time>Опубліковано {date(post.created_at)}</time><span>{post.status === 'open' ? `Активне до ${date(post.expires_at)}` : post.status === 'closed' ? 'Оголошення завершено' : 'Строк дії минув'}</span></div><p className="board-full-description">{post.description}</p>{post.location && <p className="board-location">⌖ {post.location}</p>}{(owner || staff) && <div className="board-owner-actions">{owner && <><Link className="secondary" to={`/board/${postId}/edit`}>Редагувати</Link><button className="primary" disabled={busy} onClick={() => action('status')}>{post.status === 'open' ? 'Позначити як завершене' : 'Поновити на 30 днів'}</button></>}<button className="secondary danger-button" disabled={busy} onClick={() => action('delete')}>{owner ? 'Видалити' : 'Видалити як модератор'}</button></div>}</article>{error && <p className="auth-feedback error" role="alert">{error}</p>}<AccessNote />
    {allowed && <section className="board-responses"><div className="board-response-heading"><div><p className="eyebrow">ДОМОВЛЯЙТЕСЯ ТУТ</p><h2>{owner ? 'Відгуки читачів' : 'Розмова з автором'}</h2></div><button className="secondary" onClick={refresh}>Оновити</button></div><p className="board-privacy">Повідомлення бачите лише ви та співрозмовник. Пошта й телефон профілю не публікуються.</p>{responseLoading ? <p role="status">Завантажуємо розмови…</p> : threads.length ? threads.map(thread => <Conversation key={thread._id} thread={thread} ownerName={post.owner_name} currentUserId={user._id} onUpdated={updateThread} />) : owner ? <div className="board-empty"><h3>Ще немає відгуків</h3><p>Коли хтось напише, ви отримаєте сповіщення. Розмови з’являться тут.</p></div> : post.status !== 'open' ? <div className="board-empty"><p>Це оголошення вже неактуальне. Подивіться інші на дошці.</p></div> : <form className="board-first-response" onSubmit={respond}><label>Ваш відгук<textarea required rows={4} maxLength={1000} value={text} placeholder={post.kind === 'wanted' ? 'Маю цю книгу! Можу передати…' : 'Цікавить ваша книга. Пропоную…'} onChange={event => setText(event.target.value)} disabled={busy} /></label><button className="primary" disabled={busy || !text.trim()}>{busy ? 'Надсилаємо…' : 'Відгукнутися приватно'}</button></form>}{replyError && <p role="alert" className="auth-feedback error">{replyError}</p>}</section>}
  </section>
}
