import { useCallback, useEffect, useRef, useState } from "react";
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  authApi,
  booksApi,
  moderationApi,
  notificationsApi,
  profilesApi,
  proposalsApi,
} from "./api";
import { useAuth } from "./auth";
import "./App.css";
import "./forms.css";
import { BoardTabs, BoardPage, BoardDetail, BoardEditor } from "./Board";

const genreLabels = {
  Fiction: "Художня література",
  "Non-fiction": "Нон-фікшн",
  Science: "Наука",
  History: "Історія",
  Fantasy: "Фентезі",
  "Sci-Fi": "Наукова фантастика",
  Poetry: "Поезія",
  Management: "Менеджмент",
  Mechanics: "Механіка",
  Programming: "Програмування",
  Economics: "Економіка",
};

function genreLabel(value) {
  return String(value || "").split(",").map((item) => genreLabels[item.trim()] || item.trim()).filter(Boolean).join(", ");
}

function canParticipate(user) {
  return Boolean(
    user &&
      (user.role === "admin" ||
        user.role === "moderator" ||
        (user.email_verified && user.is_approved)),
  );
}

function ManagementPagination({ page, hasNext, onPageChange }) {
  return (
    <div className="pagination" aria-label="Сторінки списку">
      <button
        className="secondary"
        disabled={page === 1}
        onClick={() => onPageChange(page - 1)}
      >
        Попередня
      </button>
      <span>Сторінка {page}</span>
      <button
        className="secondary"
        disabled={!hasNext}
        onClick={() => onPageChange(page + 1)}
      >
        Наступна
      </button>
    </div>
  );
}

const genreOptions = Object.keys(genreLabels);

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const load = async () => {
    try {
      const { data } = await notificationsApi.list();
      setItems(data);
      setOpen((value) => !value);
      setError("");
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Не вдалося завантажити сповіщення.");
    }
  };
  const markRead = async () => {
    try {
      await notificationsApi.markRead();
      setItems((current) => current.map((item) => ({ ...item, is_read: true })));
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Не вдалося позначити сповіщення прочитаними.");
    }
  };
  const unreadCount = items.filter((item) => !item.is_read).length;
  return (
    <div className="notification-wrap">
      <button className="bell" title="Сповіщення" onClick={load} aria-label={`Сповіщення, непрочитаних: ${unreadCount}`}>
        ◌{unreadCount > 0 && <span className="bell-dot" />}
      </button>
      {open && (
        <div className="notification-menu">
          <strong>Сповіщення</strong>
          {error && <p className="error">{error}</p>}
          {items.length ? (
            items
              .slice(-5)
              .reverse()
              .map((item, index) => (
                <p className={`notification-item ${item.is_read ? "" : "unread"}`} key={item.notification_id || `${item.created_at}-${index}`}>
                  {!item.is_read && <span className="notification-unread-dot" aria-label="Непрочитане" />}
                  {item.type === "new_book" && item.book_id ? (
                    <Link to={`/books/${item.book_id}`} onClick={() => setOpen(false)}>{item.message}</Link>
                  ) : item.board_post_id ? (
                    <Link to={`/board/${item.board_post_id}`} onClick={() => setOpen(false)}>{item.message}</Link>
                  ) : item.message}
                </p>
              ))
          ) : (
            <p>Нових сповіщень немає.</p>
          )}
          {unreadCount > 0 && <button className="link-button" onClick={markRead}>Позначити прочитаними</button>}
        </div>
      )}
    </div>
  );
}

function Layout() {
  const { isAuthenticated, user, logout } = useAuth();
  const [theme, setTheme] = useState(() => {
    const savedTheme = localStorage.getItem("knigoluby_theme");
    if (savedTheme === "dark") return "gray";
    return ["white", "gray", "navy"].includes(savedTheme) ? savedTheme : "white";
  });
  const [themeMenuOpen, setThemeMenuOpen] = useState(false);
  const selectTheme = (nextTheme) => {
    setTheme(nextTheme);
    localStorage.setItem("knigoluby_theme", nextTheme);
    setThemeMenuOpen(false);
  };
  const themeClass = theme === "gray" ? "theme-dark" : theme === "navy" ? "theme-navy" : "";
  return (
    <div className={`app-shell ${themeClass}`}>
      <header className="topbar">
        <Link className="brand flex flex-row items-center gap-4" to="/">
          <div className="brand-stack flex flex-col items-center justify-center">
            <img className="brand-mark" src={theme === "white" ? "/logo.png" : "/logodark.png"} alt="BookWay logo" />
            <strong className="brand-title"><span className="brand-book">Book</span><span className="brand-way">Way</span></strong>
          </div>
          <div className="h-10 w-[1px] bg-gray-500/30"></div>
          <div className="brand-tagline-wrap flex items-center">
            <span className="brand-subtitle text-[10px] md:text-xs text-gray-400 uppercase tracking-[0.2em] font-medium leading-relaxed max-w-[140px] text-left">
              простір обміну книжок
            </span>
          </div>
        </Link>
        <nav>
            <NavLink to="/">Каталог</NavLink>
          <div className="theme-picker">
            <button
              className="theme-toggle"
              onClick={() => setThemeMenuOpen((open) => !open)}
              title="Вибрати тему"
              aria-label="Вибрати тему"
              aria-expanded={themeMenuOpen}
            >
              ☼
            </button>
            {themeMenuOpen && (
              <div className="theme-menu" role="menu">
                {[['white', 'Біла'], ['gray', 'Сіра'], ['navy', 'Темно синя']].map(([value, label]) => (
                  <button
                    className={theme === value ? "active" : ""}
                    key={value}
                    onClick={() => selectTheme(value)}
                    role="menuitem"
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>
          {isAuthenticated && user && (
            <>
              {canParticipate(user) && <NavLink to="/dashboard">Моя полиця</NavLink>}
              <NavLink to="/profile">Профіль</NavLink>
              {user.role === "admin" && (
                  <NavLink className="role-link" to="/admin">
                  Адмін
                </NavLink>
              )}
              {user.role === "moderator" && (
                  <NavLink className="role-link" to="/moderation">
                  Модератор
                </NavLink>
              )}
              {canParticipate(user) && <NotificationBell />}
              <button className="link-button" onClick={logout}>
                Вийти
              </button>
            </>
          )}
          {!isAuthenticated && (
            <Link className="nav-cta" to="/login">
              Увійти
            </Link>
          )}
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Catalog />} />
          <Route path="/board" element={<BoardPage />} />
          <Route path="/board/new" element={<BoardEditor key="new-post" />} />
          <Route path="/board/:postId" element={<BoardDetail />} />
          <Route path="/board/:postId/edit" element={<BoardEditor />} />
          <Route path="/login" element={<AuthForm key="login" mode="login" />} />
          <Route path="/register" element={<AuthForm key="register" mode="register" />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="/books/:id" element={<BookDetails />} />
          <Route
            path="/dashboard"
            element={
              <ApprovedRoute>
                <Dashboard />
              </ApprovedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
          <Route path="/users/:userId" element={<PublicProfilePage />} />
          <Route
            path="/admin"
            element={
              <RoleRoute role="admin">
                <AdminPanel />
              </RoleRoute>
            }
          />
          <Route
            path="/moderation"
            element={
              <RoleRoute role="moderator">
                <>
                  <ModeratorPanel />
                  <BookManagement />
                </>
              </RoleRoute>
            }
          />
        </Routes>
      </main>
    </div>
  );
}

function ProtectedRoute({ children }) {
  const { isAuthenticated, user } = useAuth();
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}
function ApprovedRoute({ children }) {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!user) {
    return <section className="page"><p>Завантаження профілю...</p></section>;
  }
  return canParticipate(user) ? children : <Navigate to="/profile" replace />;
}
function RoleRoute({ children, role }) {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!user)
    return (
      <section className="page">
        <p>Завантаження профілю...</p>
      </section>
    );
  return user.role === role ? children : <Navigate to="/dashboard" replace />;
}

function BookCover({ book, className = "" }) {
  const [imageFailed, setImageFailed] = useState(false);
  const showImage = book.cover_image_url && !imageFailed;
  return (
    <div className={`book-cover cover-frame ${className}`}>
      {showImage ? (
        <img
          src={book.cover_image_url}
          alt={`Обкладинка: ${book.title}`}
          onError={() => setImageFailed(true)}
        />
      ) : (
        <div className="cover-fallback" aria-label="Обкладинка відсутня">
          <span className="book-icon" aria-hidden="true">▥</span>
          <small>{book.title.slice(0, 1)}</small>
        </div>
      )}
    </div>
  );
}

function getCatalogPageSize() {
  if (window.innerWidth <= 680) return 5;
  const contentWidth = Math.min(window.innerWidth - 64, 1180);
  const columns = Math.max(1, Math.floor((contentWidth + 18) / 253));
  return Math.max(5, columns * 2);
}

function Catalog() {
  const [books, setBooks] = useState([]);
  const [search, setSearch] = useState("");
  const [genre, setGenre] = useState("");
  const [availability, setAvailability] = useState("");
  const [sort, setSort] = useState("");
  const [page, setPage] = useState(1);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [pageSize, setPageSize] = useState(getCatalogPageSize);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    const updatePageSize = () => {
      const nextPageSize = getCatalogPageSize();
      setPageSize((current) => {
        if (current !== nextPageSize) setPage(1);
        return nextPageSize;
      });
    };
    window.addEventListener("resize", updatePageSize);
    return () => window.removeEventListener("resize", updatePageSize);
  }, []);
  useEffect(() => {
    setPage(1);
  }, [search, genre, availability, sort]);
  useEffect(() => {
    let active = true;
    setLoading(true);
    const params = {};
    params.page = page;
    params.page_size = pageSize;
    if (search) params.search = search;
    if (genre) params.genre = genre;
    if (availability) params.availability = availability;
    if (sort) params.sort_by = sort;
    booksApi.list(params)
      .then(({ data, headers }) => {
        if (!active) return;
        setBooks(data);
        setHasNextPage(headers["x-has-next"] === "true");
        setError("");
      })
      .catch(() => { if (active) setError("Не вдалося завантажити каталог."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [search, genre, availability, sort, page, pageSize]);
  return (
    <section className="page catalog-page">
      <div className="page-heading">
        <p className="eyebrow">БІБЛІОТЕКА BOOKWAY</p>
        <h1>Знайди наступну історію</h1>
      </div>
      <BoardTabs active="catalog" />
      <div className="catalog-tools">
        <div className="catalog-search">
          <label className="catalog-search-field">
            <span className="catalog-search-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <circle cx="10.8" cy="10.8" r="6.8" />
                <path d="m16 16 4.5 4.5" />
              </svg>
            </span>
            <input
              className="search"
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Пошук за назвою або автором"
              aria-label="Пошук за назвою або автором"
            />
            {search && (
              <button
                type="button"
                className="clear-search"
                aria-label="Очистити пошук"
                onClick={() => setSearch("")}
              >
                ×
              </button>
            )}
          </label>
        </div>
        <aside className="filters">
          <label>
            Жанр
            <select
              value={genre}
              onChange={(event) => setGenre(event.target.value)}
            >
              <option value="">Усі жанри</option>
              {genreOptions.map((genre) => <option value={genre} key={genre}>{genreLabel(genre)}</option>)}
            </select>
          </label>
          <label>
            Стан
            <select
              value={availability}
              onChange={(event) => setAvailability(event.target.value)}
            >
              <option value="">Усі книги</option>
              <option value="available">Доступні</option>
              <option value="borrowed">Позичені</option>
            </select>
          </label>
          <label>
            Сортування
            <select
              value={sort}
              onChange={(event) => setSort(event.target.value)}
            >
              <option value="">За замовчуванням</option>
              <option value="rating">За рейтингом</option>
              <option value="popularity">За популярністю (переглядами)</option>
            </select>
          </label>
        </aside>
      </div>
      {error && <p className="error">{error}</p>}
      {loading ? (
        <div className="catalog-loading" role="status" aria-live="polite">
          <img src="/logoloading.png" alt="Завантаження каталогу" />
          <span>Завантаження каталогу...</span>
        </div>
      ) : (
        <>
          <div className="book-grid">
            {books.map((book) => {
              return (
                <Link className="book-card" to={`/books/${book._id}`} key={book._id}>
                  <div className="catalog-cover-wrap">
                    <BookCover book={book} className="catalog-cover" />
                  </div>
                  <div className="book-card-content">
                    <p className="genre">{genreLabel(book.genre)}</p>
                    <h2>{book.title}</h2>
                    <p className="book-card-author">{book.author}</p>
                    <div className="book-card-meta">
                      <span className={`status ${book.status}`}>
                        <span aria-hidden="true">{book.status === "available" ? "✓" : "•"}</span>
                        {book.status === "available" ? "Доступна" : "Позичена"}
                      </span>
                      <span className="book-views"><span aria-hidden="true">◉</span> {book.views || 0} переглядів</span>
                    </div>
                    <p className="rating">★ {book.rating.toFixed(1)}</p>
                  </div>
                </Link>
              );
            })}
          </div>
          {!error && books.length === 0 && (
            <p className="empty">Каталог поки порожній.</p>
          )}
        </>
      )}
      {!loading && (page > 1 || hasNextPage) && (
        <div className="pagination" aria-label="Сторінки каталогу">
          <button className="secondary" disabled={page === 1} onClick={() => setPage((current) => current - 1)}>
            Попередня
          </button>
          <span>Сторінка {page}</span>
          <button className="secondary" disabled={!hasNextPage} onClick={() => setPage((current) => current + 1)}>
            Наступна
          </button>
        </div>
      )}
    </section>
  );
}

function BookDetails() {
  const { id } = useParams();
  const { isAuthenticated, user } = useAuth();
  const canUseActions = canParticipate(user);
  const navigate = useNavigate();
  const viewedBookId = useRef(null);
  const [book, setBook] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [message, setMessage] = useState("");
  const [toast, setToast] = useState(null);
  const [wishlisted, setWishlisted] = useState(false);
  const [review, setReview] = useState({ rating: 5, comment: "" });
  const loadReviews = () =>
    booksApi
      .reviews(id)
      .then(({ data }) => setReviews(data))
      .catch(() => {});
  useEffect(() => {
    if (viewedBookId.current === id) return;
    viewedBookId.current = id;
    booksApi
      .get(id)
      .then(({ data }) => setBook(data))
      .catch(() => setMessage("Книгу не знайдено."));
    loadReviews();
  }, [id]);
  useEffect(() => {
    if (!isAuthenticated) return;
    profilesApi.mine().then(({ data }) => setWishlisted(data.favorites.some((item) => item._id === id))).catch(() => {});
  }, [id, isAuthenticated]);
  if (!book)
    return (
      <section className="page">
        <p>{message || "Завантаження..."}</p>
      </section>
    );
  const action = async (method) => {
    if (!isAuthenticated) {
      navigate("/login", { state: { from: `/books/${id}` } });
      return;
    }
    try {
      const { data } = await booksApi[method](id);
      setBook(data);
      setMessage("Готово.");
      setToast({ type: "success", text: method === "queue" ? "Книгу додано до черги." : "Книгу успішно позичено." });
    } catch (error) {
      setToast({ type: "error", text: error.response?.data?.detail || "Не вдалося виконати дію." });
      setMessage(error.response?.data?.detail || "Дія недоступна. Спробуйте ще раз.");
    }
  };
  const currentUserId = user?.id || user?._id;
  const isCurrentReader = Boolean(user && String(book.current_reader_id) === String(currentUserId));
  const isInQueue = Boolean(user && book.queue?.some((queuedUserId) => String(queuedUserId) === String(currentUserId)));
  const queuePosition = user
    ? book.queue?.findIndex((queuedUserId) => String(queuedUserId) === String(currentUserId)) ?? -1
    : -1;
  const submitReview = async (event) => {
    event.preventDefault();
    try {
      await booksApi.addReview(id, {
        rating: Number(review.rating),
        comment: review.comment,
      });
      setReview({ rating: 5, comment: "" });
      await loadReviews();
      setMessage("Відгук додано.");
    } catch {
      setMessage("Не вдалося додати відгук.");
    }
  };
  const deleteReview = async (reviewId) => {
    if (!window.confirm("Видалити ваш відгук?")) return;
    try {
      await booksApi.deleteReview(id, reviewId);
      await loadReviews();
      setToast({ type: "success", text: "Відгук видалено. Тепер можна написати новий." });
    } catch {
      setToast({ type: "error", text: "Не вдалося видалити відгук." });
    }
  };
  const toggleFavorite = async () => {
    if (!isAuthenticated) {
      navigate("/login", { state: { from: `/books/${id}` } });
      return;
    }
    try {
      const { data } = await profilesApi.toggleFavorite(id);
      setWishlisted(data.saved);
      setToast({ type: "success", text: data.saved ? "Додано в обране." : "Видалено з обраного." });
    } catch {
      setToast({ type: "error", text: "Не вдалося оновити обране." });
    }
  };
  const leaveQueue = async () => {
    if (!isAuthenticated) {
      navigate("/login", { state: { from: `/books/${id}` } });
      return;
    }
    try {
      const { data } = await booksApi.leaveQueue(id);
      setBook(data);
      setToast({ type: "success", text: "Ви вийшли з черги." });
    } catch (error) {
      setToast({ type: "error", text: error.response?.data?.detail || "Не вдалося вийти з черги." });
    }
  };
  return (
    <section className="page detail">
      <div className="detail-main">
        <BookCover book={book} className="detail-image-cover" />
        <div>
          <p className="eyebrow">{genreLabel(book.genre)}</p>
          <h1>{book.title}</h1>
          <p className="author">{book.author}</p>
          <p className="rating large">★ {book.rating.toFixed(1)}</p>
          <p className="book-views">Переглядів сторінки: {book.views || 0}</p>
          <p className="description">
            {book.description || "Опис цієї книги ще не додано."}
          </p>
          {canUseActions ? (isCurrentReader ? <button className="primary action-disabled" disabled>Ви вже читаєте цю книгу</button> : isInQueue ? <button className="secondary" onClick={leaveQueue}>Вийти з черги</button> : <button className="primary" onClick={() => action(book.status === "available" ? "borrow" : "queue")}>{book.status === "available" ? "Почитати" : "Приєднатися до черги"}</button>) : isAuthenticated ? <p className="notice">Позичати книги та взаємодіяти з каталогом можна після підтвердження email і схвалення модератором.</p> : <button className="primary" onClick={() => action(book.status === "available" ? "borrow" : "queue")}>{book.status === "available" ? "Почитати" : "Приєднатися до черги"}</button>}
          {isInQueue && queuePosition >= 0 && <p className="queue-position">Ваш номер у черзі: <strong>#{queuePosition + 1}</strong></p>}
          {(!isAuthenticated || canUseActions) && <button className={`secondary wishlist-button ${wishlisted ? "is-saved" : ""}`} aria-pressed={wishlisted} title={wishlisted ? "Видалити з обраного" : "Додати в обране"} onClick={toggleFavorite}>
            <span aria-hidden="true">{wishlisted ? "♥" : "♡"}</span> {wishlisted ? "В улюблених" : "Додати в улюблені"}
          </button>}
          {message && <p className="notice">{message}</p>}
        </div>
      </div>
      <section className="reviews">
        <div className="section-heading">
          <p className="eyebrow">ВІДГУКИ</p>
          <h2>Що кажуть читачі</h2>
        </div>
        {reviews.length ? (
          reviews.map((item) => (
            <article className="review" key={item._id}>
              <div className="review-stars">
                {"★".repeat(item.rating)}
                {"☆".repeat(5 - item.rating)}
              </div>
              <div className="review-author"><span className="review-avatar">{(item.user_name || "К").slice(0, 1).toUpperCase()}</span><Link to={`/users/${item.user_id}`}><strong>{item.user_name || "Читач"}</strong></Link><time>{new Date(item.created_at).toLocaleDateString("uk-UA")}</time>{canUseActions && (String(item.user_id) === String(currentUserId) || user.role === "admin" || user.role === "moderator") && <button className="review-delete" onClick={() => deleteReview(item._id)}>Видалити відгук</button>}</div>
              <p>{item.comment}</p>
            </article>
          ))
        ) : (
          <p className="empty">Відгуків ще немає.</p>
        )}
        {canUseActions && (
          <form className="review-form" onSubmit={submitReview}>
            <h3>Залишити відгук</h3>
            <select
              value={review.rating}
              onChange={(event) =>
                setReview({ ...review, rating: event.target.value })
              }
            >
              <option value="5">5 зірок</option>
              <option value="4">4 зірки</option>
              <option value="3">3 зірки</option>
              <option value="2">2 зірки</option>
              <option value="1">1 зірка</option>
            </select>
            <textarea
              required
              maxLength="2000"
              value={review.comment}
              onChange={(event) =>
                setReview({ ...review, comment: event.target.value })
              }
              placeholder="Поділіться враженнями"
            />
            <button className="primary" type="submit">
              Опублікувати
            </button>
          </form>
        )}
        {isAuthenticated && !canUseActions && <p className="notice">Щоб залишити відгук, підтвердіть email і дочекайтеся схвалення модератора.</p>}
      </section>
      {toast && <div className={`toast toast-${toast.type}`} role="status"><span>{toast.text}</span><button onClick={() => setToast(null)} aria-label="Закрити">×</button></div>}
    </section>
  );
}

function requestMessage(error, fallback) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "Перевірте правильність пошти, імені та довжину пароля.";
  return fallback;
}

function PanelSearch({ value, onChange, label, placeholder }) {
  return <label className="panel-search">
    <span className="field-caption">{label}</span>
    <span className="panel-search-control">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4.5 4.5" /></svg>
      <input type="search" value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
      {value && <button type="button" aria-label="Очистити пошук" onClick={() => onChange("")}>×</button>}
    </span>
  </label>;
}

function AuthForm({ mode }) {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const isRegister = mode === "register";
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [canResend, setCanResend] = useState(false);
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    setError(""); setMessage(""); setCanResend(false); setBusy(true);
    try {
      const email = form.email.trim();
      if (!isRegister) await login({ email, password: form.password });
      else {
        await register({ ...form, name: form.name.trim(), email });
        setCanResend(true);
        setMessage(`Лист підтвердження надіслано на ${email}. Акаунт буде створено лише після переходу за посиланням у листі. Посилання дійсне 24 години.`);
        return;
      }
      navigate("/");
    } catch (requestError) {
      setCanResend([403, 409, 502].includes(requestError.response?.status));
      setError(requestMessage(requestError, "Не вдалося з’єднатися із сервером. Спробуйте ще раз."));
    } finally { setBusy(false); }
  };
  const resendVerification = async () => {
    if (busy || !form.email.trim()) return;
    setError(""); setMessage(""); setBusy(true);
    try {
      const { data } = await authApi.resendVerification({ email: form.email.trim() });
      setMessage(data.message + " Перевірте також папку «Спам».");
      setCanResend(false);
    } catch (requestError) {
      setError(requestMessage(requestError, "Не вдалося повторно надіслати лист. Спробуйте ще раз."));
    } finally { setBusy(false); }
  };
  return (
    <section className="page auth-page">
      <aside className="auth-story">
        <p className="eyebrow">СПІЛЬНОТА КНИГОЛЮБІВ</p>
        <div className="auth-book-art" aria-hidden="true"><span>Ще одна</span><strong>хороша<br />історія.</strong><i>Починається з вас</i></div>
        <h2>Книги зближують.</h2>
        <p>Знаходьте нові історії, діліться улюбленими книгами та зберігайте власну читацьку полицю.</p>
        <span className="auth-story-note">Ваша наступна книга вже чекає</span>
      </aside>
      <div className="auth-card">
        <p className="eyebrow">{isRegister ? "НОВИЙ РОЗДІЛ" : "З ПОВЕРНЕННЯМ"}</p>
        <h1>{isRegister ? "Станьте частиною історії" : "Раді вас бачити"}</h1>
        <p className="auth-intro">{isRegister ? "Створіть профіль і відкрийте для себе більше хороших книг." : "Увійдіть, щоб повернутися до своєї полиці та нових відкриттів."}</p>
        <form onSubmit={submit} className="auth-form" aria-busy={busy}>
          <fieldset disabled={busy}>
            {isRegister && <label>Ваше ім’я<input required name="name" autoComplete="name" maxLength={120} placeholder="Як до вас звертатися?" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>}
            <label>Електронна пошта<input required name="email" autoComplete="email" type="email" placeholder="you@example.com" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
            <label>Пароль<span className="password-control"><input required name="password" autoComplete={isRegister ? "new-password" : "current-password"} minLength={8} maxLength={128} type={showPassword ? "text" : "password"} placeholder={isRegister ? "Придумайте надійний пароль" : "Введіть ваш пароль"} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /><button type="button" aria-label={showPassword ? "Приховати пароль" : "Показати пароль"} aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}>{showPassword ? "Сховати" : "Показати"}</button></span></label>
            {isRegister && <small className="field-hint">Від 8 до 128 символів. Створимо акаунт після підтвердження пошти.</small>}
            <button className="primary auth-submit" type="submit">{busy ? "Зачекайте…" : isRegister ? "Підтвердити пошту" : "Увійти"}<span aria-hidden="true"> →</span></button>
          </fieldset>
        </form>
        {error && <p className="auth-feedback error" role="alert">{error}</p>}
        {message && <div className="auth-feedback success" role="status"><strong>Перевірте пошту</strong><p>{message}</p><small>Не бачите листа? Перегляньте папку «Спам».</small></div>}
        {canResend && <button className="secondary auth-resend" disabled={busy} type="button" onClick={resendVerification}>{busy ? "Надсилаємо…" : "Надіслати лист ще раз"}</button>}
        <p className="auth-switch">{isRegister ? "Вже маєте профіль?" : "Вперше у Книголюбах?"} <Link to={isRegister ? "/login" : "/register"}>{isRegister ? "Увійти" : "Зареєструватися"}</Link></p>
        <Link className="auth-back" to="/">← Повернутися до каталогу</Link>
      </div>
    </section>
  );
}

function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const verification = useRef(null);
  useEffect(() => {
    let active = true;
    setMessage(""); setError("");
    if (!token) {
      setError("У посиланні немає токена підтвердження.");
      return;
    }
    // Reuse the request during StrictMode's effect replay: tokens are single-use.
    if (verification.current?.token !== token) verification.current = { token, request: authApi.verifyEmail(token) };
    verification.current.request
      .then(({ data }) => { if (active) setMessage(data.message); })
      .catch((requestError) => { if (active) setError(requestMessage(requestError, "Не вдалося підтвердити пошту.")); });
    return () => { active = false; };
  }, [token]);
  return (
    <section className="page verification-page">
      <div className="auth-card">
        <p className="eyebrow">ПІДТВЕРДЖЕННЯ ПОШТИ</p>
        <div className="verification-icon" aria-hidden="true">{error ? "!" : message ? "✓" : "…"}</div>
        <h1>{error ? "Потрібне нове посилання" : message ? "Пошту підтверджено" : "Перевіряємо посилання…"}</h1>
        {message && <p className="auth-feedback success" role="status">{message}</p>}
        {error && <p className="auth-feedback error" role="alert">{error}</p>}
        <Link className="primary auth-submit" to="/login">{error ? "Увійти та запросити новий лист" : "Перейти до входу"}</Link>
      </div>
    </section>
  );
}

function ProposalForm({ onCreated }) {
  const [form, setForm] = useState({
    title: "",
    author: "",
    isbn: "",
    genre: "",
    description: "",
    cover_image_url: "",
    note: "",
  });
  const [message, setMessage] = useState("");
  const submit = async (event) => {
    event.preventDefault();
    try {
      await proposalsApi.create({
        ...form,
        cover_image_url: form.cover_image_url || null,
      });
      setForm({
        title: "",
        author: "",
        isbn: "",
        genre: "",
        description: "",
        cover_image_url: "",
        note: "",
      });
      setMessage("Пропозицію надіслано модератору.");
      onCreated?.();
    } catch (error) {
      setMessage(error.response?.data?.detail || "Не вдалося надіслати пропозицію.");
    }
  };
  return (
    <form className="proposal-form" onSubmit={submit}>
      <div className="section-heading">
        <p className="eyebrow">ІНІЦІАТИВА</p>
        <h2>Запропонувати книгу</h2>
        <p>Розкажіть про книгу, яку ви готові принести до полиці.</p>
      </div>
      <div className="form-grid">
        <input
          required
          placeholder="Назва книги"
          value={form.title}
          onChange={(event) => setForm({ ...form, title: event.target.value })}
        />
        <input
          required
          placeholder="Автор"
          value={form.author}
          onChange={(event) => setForm({ ...form, author: event.target.value })}
        />
        <input
          placeholder="ISBN (необов’язково)"
          value={form.isbn}
          onChange={(event) => setForm({ ...form, isbn: event.target.value })}
        />
        <select required value={form.genre} onChange={(event) => setForm({ ...form, genre: event.target.value })}>
          <option value="">Оберіть жанр</option>
          {genreOptions.map((genre) => <option value={genre} key={genre}>{genreLabel(genre)}</option>)}
        </select>
        <input
          placeholder="URL обкладинки"
          value={form.cover_image_url}
          onChange={(event) =>
            setForm({ ...form, cover_image_url: event.target.value })
          }
        />
      </div>
      <textarea
        placeholder="Короткий опис"
        value={form.description}
        onChange={(event) =>
          setForm({ ...form, description: event.target.value })
        }
      />
      <textarea
        placeholder="Коментар для модератора"
        value={form.note}
        onChange={(event) => setForm({ ...form, note: event.target.value })}
      />
      <button className="primary" type="submit">
        Надіслати пропозицію
      </button>
      {message && <p className="notice">{message}</p>}
    </form>
  );
}

function Dashboard() {
  const [notifications, setNotifications] = useState([]);
  const [borrowed, setBorrowed] = useState([]);
  const [message, setMessage] = useState("");
  const load = () => {
    notificationsApi
      .list()
      .then(({ data }) => setNotifications(data))
      .catch(() => {});
    notificationsApi
      .borrowed()
      .then(({ data }) => setBorrowed(data))
      .catch(() => {});
  };
  useEffect(() => {
    load();
  }, []);
  const returnBook = async (id, finished) => {
    try {
      await booksApi.returnBook(id, finished);
      setMessage(finished ? "Книгу повернуто до прочитаних." : "Книгу повернуто до недочитаних.");
      load();
    } catch {
      setMessage("Не вдалося повернути книгу.");
    }
  };
  return (
    <section className="page dashboard">
      <p className="eyebrow">ОСОБИСТИЙ ПРОСТІР</p>
      <h1>Моя полиця</h1>
      <section>
        <div className="section-heading">
          <h2>Зараз у вас</h2>
        </div>
        {borrowed.length ? (
          <div className="borrowed-list">
            {borrowed.map((book) => {
              const days = Math.ceil(
                (new Date(book.return_deadline).getTime() - Date.now()) /
                  86400000,
              );
              return (
                <article
                  className={`borrowed-book days-${days <= 2 ? "red" : days <= 5 ? "yellow" : "green"}`}
                  key={book._id}
                >
                  <div className="borrowed-book-info">
                    <BookCover book={book} className="shelf-cover" />
                    <div>
                    <p className="genre">{genreLabel(book.genre)}</p>
                    <h3>{book.title}</h3>
                    <p>{book.author}</p>
                  </div>
                  </div>
                  <div className="deadline">
                    <strong>{days} дн.</strong>
                    <span>до повернення</span>
                  </div>
                  <div className="shelf-actions"><button className="secondary" onClick={() => returnBook(book._id, true)}>Повернути книгу, дочитав</button><button className="secondary abandon-button" onClick={() => returnBook(book._id, false)}>Повернути книгу, не дочитав</button></div>
                </article>
              );
            })}
          </div>
        ) : (
          <p className="empty">Ви нічого не позичили.</p>
        )}
      </section>
      <ProposalForm onCreated={load} />
      <div className="dashboard-panel">
        <h2>Останні сповіщення</h2>
        {notifications.length ? (
          notifications
            .slice(-5)
            .reverse()
            .map((item, index) => (
              <p className={`notification ${item.is_read ? "" : "unread"}`} key={`${item.created_at}-${index}`}>
                {!item.is_read && <span className="notification-unread-dot" aria-label="Непрочитане" />}
                {item.board_post_id ? <Link to={`/board/${item.board_post_id}`}>{item.message} ↗</Link> : item.message}
              </p>
            ))
        ) : (
          <p>Нових сповіщень немає.</p>
        )}
      </div>
      {message && <p className="notice">{message}</p>}
    </section>
  );
}

function ProfileBookList({ title, books, empty = "Поки що немає книг." }) {
  return (
    <section className="profile-section">
      <div className="section-heading"><h2>{title}</h2></div>
      {books.length ? (
        <div className="profile-book-grid">
          {books.map((book) => (
            <Link className="profile-book" to={`/books/${book._id}`} key={book._id}>
              <BookCover book={book} />
              <div><strong>{book.title}</strong><span>{book.author}</span></div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="profile-empty">
          <span className="profile-empty-icon" aria-hidden="true">▤</span>
          <p>{empty}</p>
        </div>
      )}
    </section>
  );
}

function ProfileView({ profile, editable = false, showAccountStatus = false, onSaved }) {
  const [form, setForm] = useState({ name: profile.name, avatar_url: profile.avatar_url || "", telegram_username: profile.telegram_username || "" });
  const [editing, setEditing] = useState(false);
  const [openList, setOpenList] = useState(null);
  const [saveError, setSaveError] = useState("");
  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (saving) return;
    setSaving(true);
    try {
      await profilesApi.update({ ...form, avatar_url: form.avatar_url || null, telegram_username: form.telegram_username.trim() || null });
      setEditing(false);
      setSaveError("");
      onSaved?.();
    } catch (error) {
      const detail = error.response?.data?.detail;
      setSaveError(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map(item => item.msg.replace(/^Value error, /, "")).join(" ") : "Не вдалося зберегти профіль.");
    } finally { setSaving(false); }
  };
  const avatar = profile.avatar_url ? <img src={profile.avatar_url} alt={profile.name} /> : <span>{profile.name.slice(0, 1).toUpperCase()}</span>;
  const toggleList = (list) => setOpenList((current) => current === list ? null : list);
  const roleLabel = {
    admin: "Адміністратор",
    moderator: "Модератор",
    student: "Активний читач",
  }[profile.role] || "Читач";
  const stats = [
    { key: "read", icon: "▤", label: "Прочитано", count: profile.read_books.length },
    { key: "returned", icon: "↩", label: "Повернуто", count: profile.returned_books.length },
    { key: "unfinished", icon: "◷", label: "Недочитано", count: profile.unfinished_books.length },
    { key: "favorites", icon: "♡", label: "В обраному", count: profile.favorites.length },
  ];
  return (
    <section className="page profile-page">
      <div className="profile-hero">
        <div className="profile-avatar">{avatar}</div>
        <div className="profile-identity">
          <p className="eyebrow">ЧИТАЦЬКИЙ ПРОФІЛЬ</p>
          {editing ? (
            <div className="profile-edit">
              <input aria-label="Ім’я користувача" disabled={saving} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
              <input aria-label="URL аватарки" disabled={saving} placeholder="URL аватарки" value={form.avatar_url} onChange={(event) => setForm({ ...form, avatar_url: event.target.value })} />
              <label className="profile-telegram-field">Telegram <span>необов’язково</span><input disabled={saving} placeholder="@book_reader або https://t.me/book_reader" maxLength={80} autoCapitalize="none" spellCheck={false} aria-describedby="telegram-help" value={form.telegram_username} onChange={(event) => setForm({ ...form, telegram_username: event.target.value })} /></label>
              <small id="telegram-help" className="profile-contact-help">Додайте нік, щоб інші читачі могли написати вам. Він буде видимий у профілі. Очистіть поле, щоб прибрати контакт.</small>
              <div className="profile-edit-actions">
                <button className="primary" disabled={saving} onClick={save}>{saving ? "Зберігаємо…" : "Зберегти"}</button>
                <button className="secondary" disabled={saving} onClick={() => { setEditing(false); setForm({ name: profile.name, avatar_url: profile.avatar_url || "", telegram_username: profile.telegram_username || "" }); setSaveError(""); }}>Скасувати</button>
              </div>
              {saveError && <p className="error">{saveError}</p>}
            </div>
          ) : (
            <>
              <h1>{profile.name}</h1>
              {profile.email && <p className="profile-email">{profile.email}</p>}
              {profile.telegram_username && <a className="profile-telegram-link" href={`https://t.me/${profile.telegram_username}`} target="_blank" rel="noopener noreferrer"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="m21 4-3 16-6-5-3 3 1-5 8-6-10 5-5-2 18-6Z" /></svg><span>{editable ? `@${profile.telegram_username}` : "Написати в Telegram"}<small>{editable ? "Відкрити мій Telegram ↗" : `@${profile.telegram_username} ↗`}</small></span></a>}
              <div className="profile-badges">
                <span className="profile-badge role"><span aria-hidden="true">✦</span>{roleLabel}</span>
                {showAccountStatus && (
                  <>
                    <span className={`profile-badge ${profile.email_verified ? "verified" : "pending"}`}>
                      <span aria-hidden="true">{profile.email_verified ? "✓" : "!"}</span>
                      {profile.email_verified ? "Email підтверджено" : "Email не підтверджено"}
                    </span>
                    <span className={`profile-badge ${profile.is_approved ? "verified" : "pending"}`}>
                      <span aria-hidden="true">{profile.is_approved ? "✓" : "!"}</span>
                      {profile.is_approved ? "Акаунт схвалено" : "Очікує схвалення"}
                    </span>
                  </>
                )}
              </div>
              {editable && (
                <button className="secondary profile-edit-button" onClick={() => setEditing(true)}>
                  <span aria-hidden="true">✎</span> Редагувати профіль
                </button>
              )}
            </>
          )}
        </div>
      </div>
      <div className="profile-stats">
        {stats.map((stat) => (
          <button
            className={`profile-stat ${openList === stat.key ? "is-active" : ""}`}
            key={stat.key}
            aria-pressed={openList === stat.key}
            onClick={() => toggleList(stat.key)}
          >
            <span className={`profile-stat-icon ${stat.key}`} aria-hidden="true">{stat.icon}</span>
            <span className="profile-stat-copy"><strong>{stat.count}</strong><span>{stat.label}</span></span>
          </button>
        ))}
      </div>
      <ProfileBookList title="Зараз читає" books={profile.currently_reading} />
      {openList === "favorites" && <ProfileBookList title="Додане в обране" books={profile.favorites} />}
      {openList === "read" && <ProfileBookList title="Прочитані книги" books={profile.read_books} />}
      {openList === "returned" && <ProfileBookList title="Повернуті книги" books={profile.returned_books} />}
      {openList === "unfinished" && <ProfileBookList title="Недочитані книги" books={profile.unfinished_books} />}
      <ProfileBookList title="Бажаю прочитати" books={profile.want_to_read_books} />
      <section className="profile-section">
        <div className="section-heading"><h2>Відгуки ({profile.reviews.length})</h2></div>
        {profile.reviews.length ? profile.reviews.map((review) => (
          <article className="profile-review" key={review._id}>
            <div className="profile-review-heading">
              <div className="review-stars" aria-label={`Оцінка: ${review.rating} з 5`}>{"★".repeat(review.rating)}{"☆".repeat(5 - review.rating)}</div>
              <time>{new Date(review.created_at).toLocaleDateString("uk-UA")}</time>
            </div>
            <Link className="review-book-link" to={`/books/${review.book_id}`}>{review.book_title || "Книга"} <span aria-hidden="true">↗</span></Link>
            <p>{review.comment}</p>
          </article>
        )) : <p className="empty">Цей читач ще не залишав відгуків.</p>}
      </section>
    </section>
  );
}

function ProfilePage() {
  const { isAuthenticated } = useAuth();
  const [profile, setProfile] = useState(null); const [error, setError] = useState("");
  const load = () => profilesApi.mine().then(({ data }) => setProfile(data)).catch(() => setError("Не вдалося завантажити профіль."));
  useEffect(() => { if (isAuthenticated) load(); }, [isAuthenticated]);
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (error) return <section className="page"><p className="error">{error}</p></section>;
  return profile ? <ProfileView profile={profile} editable={canParticipate(profile)} showAccountStatus onSaved={load} /> : <section className="page"><p>Завантаження профілю...</p></section>;
}

function PublicProfilePage() {
  const { userId } = useParams(); const [profile, setProfile] = useState(null); const [error, setError] = useState("");
  useEffect(() => { profilesApi.get(userId).then(({ data }) => setProfile(data)).catch(() => setError("Профіль не знайдено.")); }, [userId]);
  if (error) return <section className="page"><p className="error">{error}</p></section>;
  return profile ? <ProfileView profile={profile} /> : <section className="page"><p>Завантаження профілю...</p></section>;
}

function BookAdminPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [form, setForm] = useState({
    title: "",
    author: "",
    isbn: "",
    genre: "",
    description: "",
    cover_image_url: "",
  });
  const [message, setMessage] = useState("");
  const submit = async (event) => {
    event.preventDefault();
    try {
      await booksApi.create({
        ...form,
        cover_image_url: form.cover_image_url || null,
      });
      setForm({
        title: "",
        author: "",
        isbn: "",
        genre: "",
        description: "",
        cover_image_url: "",
      });
      setMessage("Книгу додано до каталогу.");
    } catch (error) {
      setMessage(error.response?.data?.detail || "Не вдалося додати книгу.");
    }
  };
  return (
    <section className="management-section book-admin-section">
      <div className="book-admin-heading">
        <div className="section-heading">
          <p className="eyebrow">BOOKS</p>
          <h2>Керування каталогом</h2>
        </div>
        <button
          className="primary"
          type="button"
          aria-expanded={isOpen}
          onClick={() => setIsOpen((open) => !open)}
        >
          {isOpen ? "Скасувати" : "Додати нову книгу"}
        </button>
      </div>
      {isOpen && (
        <form className="management-form" onSubmit={submit}>
          <h2>Нова книга</h2>
          <div className="form-grid">
            <input
              required
              placeholder="Назва книги"
              value={form.title}
              onChange={(event) =>
                setForm({ ...form, title: event.target.value })
              }
            />
            <input
              required
              placeholder="Автор"
              value={form.author}
              onChange={(event) =>
                setForm({ ...form, author: event.target.value })
              }
            />
            <input
              placeholder="ISBN (необов’язково)"
              value={form.isbn}
              onChange={(event) => setForm({ ...form, isbn: event.target.value })}
            />
            <select required value={form.genre} onChange={(event) => setForm({ ...form, genre: event.target.value })}>
              <option value="">Оберіть жанр</option>
              {genreOptions.map((genre) => <option value={genre} key={genre}>{genreLabel(genre)}</option>)}
            </select>
            <input
              placeholder="URL обкладинки"
              value={form.cover_image_url}
              onChange={(event) =>
                setForm({ ...form, cover_image_url: event.target.value })
              }
            />
          </div>
          <textarea
            placeholder="Опис книги"
            value={form.description}
            onChange={(event) =>
              setForm({ ...form, description: event.target.value })
            }
          />
          <button className="primary" type="submit">
            Додати до каталогу
          </button>
        </form>
      )}
      {message && <p className="notice">{message}</p>}
    </section>
  );
}

function ModeratorPanel() {
  const [proposals, setProposals] = useState([]);
  const [message, setMessage] = useState("");
  const [activeTab, setActiveTab] = useState("proposals");
  const [userCount, setUserCount] = useState(0);
  const loadProposals = () => {
    moderationApi
      .proposals()
      .then(({ data }) => setProposals(data))
      .catch(() => {});
  };
  useEffect(() => { loadProposals(); }, []);
  const decide = async (id, status) => {
    try {
      await moderationApi.decideProposal(id, { status });
      setMessage(
        status === "approved"
          ? "Книгу додано до каталогу."
          : "Пропозицію відхилено.",
      );
      loadProposals();
    } catch {
      setMessage("Не вдалося оновити пропозицію.");
    }
  };
  return (
    <section className="page moderator-page">
      <div className="panel-hero moderator-hero">
        <p className="eyebrow">MODERATOR CONTROL</p>
        <h1>Панель модератора</h1>
        <p>
          Ви керуєте довірою спільноти: вирішуйте, які книги потраплять на
          полицю, і призначайте адміністраторів.
        </p>
      </div>
      <BookAdminPanel />
      {message && <p className="notice">{message}</p>}
      <div className="workspace-tabs" role="tablist" aria-label="Розділи модератора">
        <button className={activeTab === "proposals" ? "active" : ""} onClick={() => setActiveTab("proposals")} role="tab" aria-selected={activeTab === "proposals"}>Пропозиції <span>{proposals.filter((item) => item.status === "pending").length}</span></button>
        <button className={activeTab === "users" ? "active" : ""} onClick={() => setActiveTab("users")} role="tab" aria-selected={activeTab === "users"}>Користувачі <span>{userCount}</span></button>
      </div>
      {activeTab === "proposals" && <section className="management-section">
        <div className="section-heading">
          <p className="eyebrow">INBOX</p>
          <h2>Пропозиції студентів</h2>
        </div>
        <div className="proposal-list">
          {proposals.length ? (
            proposals.map((proposal) => (
              <article className="proposal-card" key={proposal._id}>
                <div>
                  <span className={`proposal-status ${proposal.status}`}>
                    {proposal.status === "pending"
                      ? "На розгляді"
                      : proposal.status === "approved"
                        ? "Схвалено"
                        : "Відхилено"}
                  </span>
                  <h3>{proposal.title}</h3>
                  <p>
                    {proposal.author} · {proposal.genre}
                  </p>
                  <p>{proposal.description || "Без опису."}</p>
                  {proposal.note && (
                    <small>Коментар студента: {proposal.note}</small>
                  )}
                </div>
                {proposal.status === "pending" && (
                  <div className="proposal-actions">
                    <button
                      className="primary"
                      onClick={() => decide(proposal._id, "approved")}
                    >
                      Схвалити
                    </button>
                    <button
                      className="secondary"
                      onClick={() => decide(proposal._id, "rejected")}
                    >
                      Відхилити
                    </button>
                  </div>
                )}
              </article>
            ))
          ) : (
            <p className="empty">Нових пропозицій немає.</p>
          )}
        </div>
      </section>}
      {activeTab === "users" && (
        <UserManagementPanel allowRoleChanges onCountChange={setUserCount} />
      )}
    </section>
  );
}

function BookManagement() {
  const [books, setBooks] = useState([]);
  const [bookSearch, setBookSearch] = useState("");
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    title: "",
    author: "",
    isbn: "",
    genre: "",
    description: "",
    cover_image_url: "",
  });
  const [message, setMessage] = useState("");
  const load = useCallback(() =>
    booksApi
      .list({ page, page_size: 10, search: bookSearch.trim() || undefined })
      .then(({ data, headers }) => {
        setBooks(data);
        setHasNext(headers["x-has-next"] === "true");
        if (data.length === 0 && page > 1) setPage((current) => current - 1);
      })
      .catch(() => setMessage("Не вдалося завантажити книги.")), [page, bookSearch]);
  useEffect(() => {
    load();
  }, [load]);
  const startEdit = (book) => {
    setEditing(book._id);
    setForm({
      title: book.title,
      author: book.author,
      isbn: book.isbn || "",
      genre: String(book.genre || "").split(",").map((item) => item.trim()).filter(Boolean),
      description: book.description || "",
      cover_image_url: book.cover_image_url || "",
    });
  };
  const save = async () => {
    try {
      await booksApi.update(editing, {
        ...form,
        genre: form.genre.join(", "),
        cover_image_url: form.cover_image_url || null,
      });
      setEditing(null);
      setMessage("Книгу оновлено.");
      load();
    } catch (error) {
      setMessage(error.response?.data?.detail || "Не вдалося оновити книгу.");
    }
  };
  const remove = async (id) => {
    if (!window.confirm("Видалити цю книгу з каталогу?")) return;
    try {
      await booksApi.remove(id);
      setMessage("Книгу видалено.");
      load();
    } catch {
      setMessage("Не вдалося видалити книгу.");
    }
  };
  return (
    <section className="management-section book-management">
      <div className="section-heading">
        <p className="eyebrow">КАТАЛОГ</p>
        <h2>Книги на полиці</h2>
        <p>Редагуйте дані або прибирайте застарілі позиції.</p>
      </div>
      <PanelSearch label="Пошук у каталозі" placeholder="Назва книги або автор…" value={bookSearch} onChange={(value) => { setBookSearch(value); setPage(1); }} />
      {message && <p className="notice">{message}</p>}
      <div className="managed-books">
        {books.map((book) =>
          editing === book._id ? (
            <article className="managed-book editing-book" key={book._id}>
              <p className="editing-label">Ви редагуєте книгу</p>
              <div className="proposal-edit-grid">
                <label>Назва<input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
                <label>Автор<input value={form.author} onChange={(event) => setForm({ ...form, author: event.target.value })} /></label>
                <label>ISBN<input value={form.isbn} onChange={(event) => setForm({ ...form, isbn: event.target.value })} /></label>
                <label className="genre-picker">Жанри<select multiple value={form.genre} onChange={(event) => setForm({ ...form, genre: Array.from(event.target.selectedOptions, (option) => option.value) })}>{genreOptions.map((genre) => <option value={genre} key={genre}>{genreLabel(genre)}</option>)}</select><small>Можна вибрати кілька жанрів: Ctrl/Cmd + клік.</small></label>
                <label>URL обкладинки<input value={form.cover_image_url} placeholder="URL обкладинки" onChange={(event) => setForm({ ...form, cover_image_url: event.target.value })} /></label>
                <label>Опис<textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
              </div>
              <div className="proposal-actions">
                <button className="primary" onClick={save}>
                  Зберегти
                </button>
                <button className="secondary" onClick={() => setEditing(null)}>
                  Скасувати
                </button>
              </div>
            </article>
          ) : (
            <article className="managed-book" key={book._id}>
              <div>
                <span className={`status ${book.status}`}>
                  {book.status === "available" ? "Доступна" : "Позичена"}
                </span>
                <h3>{book.title}</h3>
                <p>
                    {book.author} · {genreLabel(book.genre)}
                </p>
              </div>
              <div className="proposal-actions">
                <button className="secondary" onClick={() => startEdit(book)}>
                  Редагувати
                </button>
                <button
                  className="secondary danger-button"
                  onClick={() => remove(book._id)}
                >
                  Видалити
                </button>
              </div>
            </article>
          ),
        )}
        {!books.length && <p className="empty">Книг не знайдено.</p>}
      </div>
      <ManagementPagination page={page} hasNext={hasNext} onPageChange={setPage} />
    </section>
  );
}

function StaffProposalCard({ proposal, onChange }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    title: proposal.title,
    author: proposal.author,
    isbn: proposal.isbn || "",
    genre: proposal.genre,
    description: proposal.description || "",
    cover_image_url: proposal.cover_image_url || "",
    note: proposal.note || "",
  });
  const [message, setMessage] = useState("");
  const save = async () => {
    try {
      await moderationApi.editProposal(proposal._id, {
        ...form,
        cover_image_url: form.cover_image_url || null,
      });
      setEditing(false);
      setMessage("Зміни збережено.");
      onChange();
    } catch (error) {
      setMessage(error.response?.data?.detail || "Не вдалося зберегти зміни.");
    }
  };
  const decide = async (status) => {
    try {
      await moderationApi.decideProposal(proposal._id, { status });
      onChange();
    } catch {
      setMessage("Не вдалося оновити статус.");
    }
  };
  return (
    <article className="proposal-card">
      <div className="proposal-content">
        <span className={`proposal-status ${proposal.status}`}>
          {proposal.status === "pending"
            ? "На розгляді"
            : proposal.status === "approved"
              ? "Схвалено"
              : "Відхилено"}
        </span>
        {editing ? (
          <div className="proposal-edit-grid">
            <label>Назва<input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
            <label>Автор<input value={form.author} onChange={(event) => setForm({ ...form, author: event.target.value })} /></label>
            <label>Жанр<input value={form.genre} onChange={(event) => setForm({ ...form, genre: event.target.value })} /></label>
            <label>URL обкладинки<input value={form.cover_image_url} placeholder="URL обкладинки" onChange={(event) => setForm({ ...form, cover_image_url: event.target.value })} /></label>
            <label>Опис<textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label>
            <label>Коментар модератора<textarea value={form.note} placeholder="Коментар модератора" onChange={(event) => setForm({ ...form, note: event.target.value })} /></label>
          </div>
        ) : (
          <>
            <h3>{proposal.title}</h3>
            <p>
              {proposal.author} · {proposal.genre}
            </p>
            <p>{proposal.description || "Без опису."}</p>
            {proposal.note && <small>Коментар: {proposal.note}</small>}
          </>
        )}
      </div>
      {proposal.status === "pending" && (
        <div className="proposal-actions">
          {editing ? (
            <>
              <button className="primary" onClick={save}>
                Зберегти
              </button>
              <button className="secondary" onClick={() => setEditing(false)}>
                Скасувати
              </button>
            </>
          ) : (
            <>
              <button className="secondary" onClick={() => setEditing(true)}>
                Редагувати
              </button>
              <button className="primary" onClick={() => decide("approved")}>
                Схвалити
              </button>
              <button
                className="secondary danger-button"
                onClick={() => decide("rejected")}
              >
                Відхилити
              </button>
            </>
          )}
          {message && <small>{message}</small>}
        </div>
      )}
    </article>
  );
}

function StaffProposalInbox() {
  const [proposals, setProposals] = useState([]);
  const [message, setMessage] = useState("");
  const load = () =>
    moderationApi
      .proposals()
      .then(({ data }) => setProposals(data))
      .catch(() => setMessage("Не вдалося завантажити пропозиції."));
  useEffect(() => {
    load();
  }, []);
  return (
    <section className="management-section staff-inbox">
      <div className="section-heading">
        <p className="eyebrow">INBOX</p>
        <h2>Пропозиції студентів</h2>
        <p>Перевіряйте, редагуйте й підтверджуйте книги перед публікацією.</p>
      </div>
      {message && <p className="error">{message}</p>}
      <div className="proposal-list">
        {proposals.length ? (
          proposals.map((proposal) => (
            <StaffProposalCard
              key={proposal._id}
              proposal={proposal}
              onChange={load}
            />
          ))
        ) : (
          <p className="empty">Нових пропозицій немає.</p>
        )}
      </div>
    </section>
  );
}

function AdminPanel() {
  return (
    <section className="page admin-page">
      <div className="panel-hero">
        <p className="eyebrow">ADMIN WORKSPACE</p>
        <h1>Панель адміністратора</h1>
        <p>Керуйте каталогом, пропозиціями та користувачами.</p>
      </div>
      <BookAdminPanel />
      <BookManagement />
      <StaffProposalInbox />
      <UserApprovalPanel />
    </section>
  );
}

function UserApprovalPanel() {
  return <UserManagementPanel />;
}

function UserManagementPanel({ allowRoleChanges = false, onCountChange }) {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [message, setMessage] = useState("");
  const load = useCallback(() =>
    moderationApi.users({
      page,
      page_size: 10,
      search: search.trim() || undefined,
    }).then(({ data, headers }) => {
      setUsers(data);
      setHasNext(headers["x-has-next"] === "true");
      onCountChange?.(Number(headers["x-total-count"] || 0));
      if (data.length === 0 && page > 1) setPage((current) => current - 1);
    }), [page, search, onCountChange]);
  useEffect(() => {
    load().catch(() => setMessage("Не вдалося завантажити користувачів."));
  }, [load]);
  const changeApproval = async (user) => {
    try {
      await moderationApi.updateApproval(user._id, !user.is_approved);
      setMessage(user.is_approved ? "Схвалення користувача скасовано." : "Користувача схвалено.");
      await load();
    } catch (error) {
      setMessage(error.response?.data?.detail || "Не вдалося змінити статус користувача.");
    }
  };
  const changeRole = async (userId, role) => {
    try {
      await moderationApi.updateRole(userId, role);
      setMessage("Роль користувача змінено.");
      await load();
    } catch (error) {
      setMessage(error.response?.data?.detail || "Не вдалося змінити роль.");
    }
  };
  const deleteUser = async (user) => {
    if (!window.confirm(`Видалити акаунт користувача «${user.name}»? Цю дію не можна скасувати.`)) return;
    try {
      await moderationApi.deleteUser(user._id);
      setMessage(`Акаунт користувача «${user.name}» видалено.`);
      await load();
    } catch (error) {
      setMessage(error.response?.data?.detail || "Не вдалося видалити акаунт.");
    }
  };
  return (
    <section className="management-section">
      <div className="section-heading">
        <p className="eyebrow">СПІЛЬНОТА</p>
        <h2>Користувачі платформи</h2>
      </div>
      {message && <p className="notice">{message}</p>}
      <PanelSearch label="Знайти читача" placeholder="Ім’я або електронна пошта…" value={search} onChange={(value) => { setSearch(value); setPage(1); }} />
      <div className="user-list">
        {users.map((user) => (
          <article className="user-row" key={user._id}>
            <div>
              <strong>{user.name}</strong>
              <span>{user.email}</span>
              <span>{user.email_verified ? "Email підтверджено" : "Email не підтверджено"}</span>
              <span>
                {user.role === "admin" ? "Адміністратор" : user.role === "moderator" ? "Модератор" : user.is_approved ? "Схвалений" : "Очікує схвалення"}
              </span>
            </div>
            <div className="user-actions">
              {user.role === "student" && (
                <button
                  className={user.is_approved ? "secondary" : "primary"}
                  disabled={!user.email_verified}
                  onClick={() => changeApproval(user)}
                >
                  {user.is_approved ? "Скасувати схвалення" : "Схвалити"}
                </button>
              )}
              {allowRoleChanges && (
                <select
                  value={user.role}
                  disabled={user.role === "moderator" || user._id === currentUser?.id || user._id === currentUser?._id}
                  onChange={(event) => changeRole(user._id, event.target.value)}
                >
                  <option value="student">Студент</option>
                  <option value="admin">Адмін</option>
                  <option value="moderator">Модератор</option>
                </select>
              )}
              <button
                className="secondary danger-button"
                disabled={user._id === currentUser?.id || user._id === currentUser?._id}
                onClick={() => deleteUser(user)}
              >
                Видалити акаунт
              </button>
            </div>
          </article>
        ))}
        {!users.length && <p className="empty">Користувачів не знайдено.</p>}
      </div>
      <ManagementPagination page={page} hasNext={hasNext} onPageChange={setPage} />
    </section>
  );
}

export default function App() {
  return <Layout />;
}
