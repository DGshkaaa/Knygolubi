import { useEffect, useState } from "react";
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useNavigate,
  useParams,
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

const genreOptions = Object.keys(genreLabels);

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const load = async () => {
    try {
      const { data } = await notificationsApi.list();
      setItems(data);
      setOpen((value) => !value);
    } catch {
      setItems([]);
    }
  };
  return (
    <div className="notification-wrap">
      <button className="bell" title="Сповіщення" onClick={load}>
        ◌<span className="bell-dot" />
      </button>
      {open && (
        <div className="notification-menu">
          <strong>Сповіщення</strong>
          {items.length ? (
            items
              .slice(-5)
              .reverse()
              .map((item, index) => (
                <p key={`${item.created_at}-${index}`}>{item.message}</p>
              ))
          ) : (
            <p>Нових сповіщень немає.</p>
          )}
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
                <NavLink to="/dashboard">Моя полиця</NavLink>
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
              <NotificationBell />
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
          <Route path="/login" element={<AuthForm mode="login" />} />
          <Route path="/register" element={<AuthForm mode="register" />} />
          <Route path="/books/:id" element={<BookDetails />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
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
    setLoading(true);
    const params = {};
    if (search) params.search = search;
    if (genre) params.genre = genre;
    if (availability) params.availability = availability;
    if (sort) params.sort_by = sort;
    params.page = page;
    params.page_size = pageSize;
    booksApi
      .list(params)
      .then(({ data, headers }) => {
        setBooks(data);
        setHasNextPage(headers["x-has-next"] === "true");
        setError("");
      })
      .catch(() => setError("Не вдалося завантажити каталог."))
      .finally(() => setLoading(false));
  }, [search, genre, availability, sort, page, pageSize]);
  return (
    <section className="page catalog-page">
      <div className="page-heading">
        <p className="eyebrow">COLLEGE BOOKSHELF</p>
        <h1>Знайди наступну історію</h1>
      </div>
      <div className="catalog-tools">
        <input
          className="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Пошук за назвою або автором"
        />
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
            {books.map((book) => (
              <Link className="book-card" to={`/books/${book._id}`} key={book._id}>
                <BookCover book={book} />
                <div>
                  <p className="genre">{genreLabel(book.genre)}</p>
                  <h2>{book.title}</h2>
                  <p>{book.author}</p>
                  <p className="rating">★ {book.rating.toFixed(1)}</p>
                  <span className={`status ${book.status}`}>
                    {book.status === "available" ? "Доступна" : "Позичена"}
                  </span>
                </div>
              </Link>
            ))}
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
  const navigate = useNavigate();
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
          <p className="description">
            {book.description || "Опис цієї книги ще не додано."}
          </p>
          {isCurrentReader ? <button className="primary action-disabled" disabled>Ви вже читаєте цю книгу</button> : isInQueue ? <button className="secondary" onClick={leaveQueue}>Вийти з черги</button> : <button className="primary" onClick={() => action(book.status === "available" ? "borrow" : "queue")}>{book.status === "available" ? "Почитати" : "Приєднатися до черги"}</button>}
          <button className={`secondary wishlist-button ${wishlisted ? "is-saved" : ""}`} aria-pressed={wishlisted} title={wishlisted ? "Видалити з обраного" : "Додати в обране"} onClick={toggleFavorite}>
            <span aria-hidden="true">{wishlisted ? "♥" : "♡"}</span> {wishlisted ? "В улюблених" : "Додати в улюблені"}
          </button>
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
              <div className="review-author"><span className="review-avatar">{(item.user_name || "К").slice(0, 1).toUpperCase()}</span><Link to={`/users/${item.user_id}`}><strong>{item.user_name || "Читач"}</strong></Link><time>{new Date(item.created_at).toLocaleDateString("uk-UA")}</time>{user && (String(item.user_id) === String(currentUserId) || user.role === "admin" || user.role === "moderator") && <button className="review-delete" onClick={() => deleteReview(item._id)}>Видалити відгук</button>}</div>
              <p>{item.comment}</p>
            </article>
          ))
        ) : (
          <p className="empty">Відгуків ще немає.</p>
        )}
        {isAuthenticated && (
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
      </section>
      {toast && <div className={`toast toast-${toast.type}`} role="status"><span>{toast.text}</span><button onClick={() => setToast(null)} aria-label="Закрити">×</button></div>}
    </section>
  );
}

function AuthForm({ mode }) {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const submit = async (event) => {
    event.preventDefault();
    try {
      if (mode === "login")
        await login({ email: form.email, password: form.password });
      else await register(form);
      navigate(mode === "login" ? "/" : "/login");
    } catch {
      setError("Перевірте дані та спробуйте ще раз.");
    }
  };
  return (
    <section className="page auth-page">
      <p className="eyebrow">КНИГОЛЮБИ</p>
      <h1>
        {mode === "login" ? "Раді вас бачити" : "Створіть читацький профіль"}
      </h1>
      <form onSubmit={submit}>
        {mode === "register" && (
          <input
            required
            placeholder="Ім’я"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        )}
        <input
          required
          type="email"
          placeholder="Email"
          value={form.email}
          onChange={(event) => setForm({ ...form, email: event.target.value })}
        />
        <input
          required
          minLength="8"
          type="password"
          placeholder="Пароль"
          value={form.password}
          onChange={(event) =>
            setForm({ ...form, password: event.target.value })
          }
        />
        <button className="primary" type="submit">
          {mode === "login" ? "Увійти" : "Зареєструватися"}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      <Link to={mode === "login" ? "/register" : "/login"}>
        {mode === "login" ? "Ще немає профілю?" : "Вже маєте профіль?"}
      </Link>
    </section>
  );
}

function ProposalForm({ onCreated }) {
  const [form, setForm] = useState({
    title: "",
    author: "",
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
        genre: "",
        description: "",
        cover_image_url: "",
        note: "",
      });
      setMessage("Пропозицію надіслано модератору.");
      onCreated?.();
    } catch {
      setMessage("Не вдалося надіслати пропозицію.");
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
              <p className="notification" key={`${item.created_at}-${index}`}>
                {item.message}
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
  return <section className="profile-section"><div className="section-heading"><h2>{title}</h2></div>{books.length ? <div className="profile-book-grid">{books.map((book) => <Link className="profile-book" to={`/books/${book._id}`} key={book._id}><BookCover book={book} /><div><strong>{book.title}</strong><span>{book.author}</span></div></Link>)}</div> : <p className="empty">{empty}</p>}</section>;
}

function ProfileView({ profile, editable = false, onSaved }) {
  const [form, setForm] = useState({ name: profile.name, avatar_url: profile.avatar_url || "" });
  const [editing, setEditing] = useState(false);
  const [openList, setOpenList] = useState(null);
  const save = async () => { try { await profilesApi.update({ ...form, avatar_url: form.avatar_url || null }); setEditing(false); onSaved?.(); } catch { /* profile remains editable */ } };
  const avatar = profile.avatar_url ? <img src={profile.avatar_url} alt={profile.name} /> : <span>{profile.name.slice(0, 1).toUpperCase()}</span>;
  const toggleList = (list) => setOpenList((current) => current === list ? null : list);
  return <section className="page profile-page"><div className="profile-hero"><div className="profile-avatar">{avatar}</div><div><p className="eyebrow">ЧИТАЦЬКИЙ ПРОФІЛЬ</p>{editing ? <div className="profile-edit"><input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /><input placeholder="URL аватарки" value={form.avatar_url} onChange={(event) => setForm({ ...form, avatar_url: event.target.value })} /><button className="primary" onClick={save}>Зберегти</button></div> : <><h1>{profile.name}</h1><p>{profile.email}</p>{editable && <button className="secondary" onClick={() => setEditing(true)}>Редагувати профіль</button>}</>}</div></div><div className="profile-stats"><button className={openList === "read" ? "is-active" : ""} onClick={() => toggleList("read")}><strong>{profile.read_books.length}</strong> прочитано</button><button className={openList === "returned" ? "is-active" : ""} onClick={() => toggleList("returned")}><strong>{profile.returned_books.length}</strong> повернуто</button><button className={openList === "unfinished" ? "is-active" : ""} onClick={() => toggleList("unfinished")}><strong>{profile.unfinished_books.length}</strong> недочитано</button><button className={openList === "favorites" ? "is-active" : ""} onClick={() => toggleList("favorites")}><strong>{profile.favorites.length}</strong> в обраному</button></div><ProfileBookList title="Зараз читає" books={profile.currently_reading} />{openList === "favorites" && <ProfileBookList title="Додане в обране" books={profile.favorites} />}{openList === "read" && <ProfileBookList title="Прочитані книги" books={profile.read_books} />}{openList === "returned" && <ProfileBookList title="Повернуті книги" books={profile.returned_books} />}{openList === "unfinished" && <ProfileBookList title="Недочитані книги" books={profile.unfinished_books} />}<ProfileBookList title="Бажаю прочитати" books={profile.want_to_read_books} /><section className="profile-section"><div className="section-heading"><h2>Відгуки ({profile.reviews.length})</h2></div>{profile.reviews.length ? profile.reviews.map((review) => <article className="profile-review" key={review._id}><div className="review-stars">{"★".repeat(review.rating)}{"☆".repeat(5 - review.rating)}</div><Link className="review-book-link" to={`/books/${review.book_id}`}>{review.book_title || "Книга"}</Link><p>{review.comment}</p><time>{new Date(review.created_at).toLocaleDateString("uk-UA")}</time></article>) : <p className="empty">Цей читач ще не залишав відгуків.</p>}</section></section>;
}

function ProfilePage() {
  const { isAuthenticated } = useAuth();
  const [profile, setProfile] = useState(null); const [error, setError] = useState("");
  const load = () => profilesApi.mine().then(({ data }) => setProfile(data)).catch(() => setError("Не вдалося завантажити профіль."));
  useEffect(() => { if (isAuthenticated) load(); }, [isAuthenticated]);
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (error) return <section className="page"><p className="error">{error}</p></section>;
  return profile ? <ProfileView profile={profile} editable onSaved={load} /> : <section className="page"><p>Завантаження профілю...</p></section>;
}

function PublicProfilePage() {
  const { userId } = useParams(); const [profile, setProfile] = useState(null); const [error, setError] = useState("");
  useEffect(() => { profilesApi.get(userId).then(({ data }) => setProfile(data)).catch(() => setError("Профіль не знайдено.")); }, [userId]);
  if (error) return <section className="page"><p className="error">{error}</p></section>;
  return profile ? <ProfileView profile={profile} /> : <section className="page"><p>Завантаження профілю...</p></section>;
}

function BookAdminPanel() {
  const [form, setForm] = useState({
    title: "",
    author: "",
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
        genre: "",
        description: "",
        cover_image_url: "",
      });
      setMessage("Книгу додано до каталогу.");
    } catch {
      setMessage("Не вдалося додати книгу.");
    }
  };
  return (
    <section className="page admin-page">
      <div className="panel-hero">
        <p className="eyebrow">ADMIN WORKSPACE</p>
        <h1>Керування каталогом</h1>
        <p>
          Додавайте книги, які вже пройшли модерацію, і підтримуйте полицю
          актуальною.
        </p>
      </div>
      <form className="management-form" onSubmit={submit}>
        <h2>Додати книгу</h2>
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
        {message && <p className="notice">{message}</p>}
      </form>
    </section>
  );
}

function ModeratorPanel() {
  const [proposals, setProposals] = useState([]);
  const [users, setUsers] = useState([]);
  const [userSearch, setUserSearch] = useState("");
  const [message, setMessage] = useState("");
  const [activeTab, setActiveTab] = useState("proposals");
  const load = () => {
    moderationApi
      .proposals()
      .then(({ data }) => setProposals(data))
      .catch(() => {});
    moderationApi
      .users()
      .then(({ data }) => setUsers(data))
      .catch(() => {});
  };
  useEffect(() => { load(); }, []);
  const decide = async (id, status) => {
    try {
      await moderationApi.decideProposal(id, { status });
      setMessage(
        status === "approved"
          ? "Книгу додано до каталогу."
          : "Пропозицію відхилено.",
      );
      load();
    } catch {
      setMessage("Не вдалося оновити пропозицію.");
    }
  };
  const changeRole = async (id, role) => {
    try {
      await moderationApi.updateRole(id, role);
      load();
    } catch {
      setMessage("Не вдалося змінити роль.");
    }
  };
  const visibleUsers = users.filter((user) => `${user.name} ${user.email}`.toLowerCase().includes(userSearch.trim().toLowerCase()));
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
      {message && <p className="notice">{message}</p>}
      <div className="workspace-tabs" role="tablist" aria-label="Розділи модератора">
        <button className={activeTab === "proposals" ? "active" : ""} onClick={() => setActiveTab("proposals")} role="tab" aria-selected={activeTab === "proposals"}>Пропозиції <span>{proposals.filter((item) => item.status === "pending").length}</span></button>
        <button className={activeTab === "users" ? "active" : ""} onClick={() => setActiveTab("users")} role="tab" aria-selected={activeTab === "users"}>Користувачі <span>{users.length}</span></button>
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
      {activeTab === "users" && <section className="management-section">
        <div className="section-heading">
          <p className="eyebrow">PEOPLE</p>
          <h2>Команда платформи</h2>
        </div>
        <input className="management-search" placeholder="Пошук користувача за nickname або username" value={userSearch} onChange={(event) => setUserSearch(event.target.value)} />
        <div className="user-list">
          {visibleUsers.map((user) => (
            <article className="user-row" key={user._id}>
              <div>
                <strong>{user.name}</strong>
                <span>{user.email}</span>
              </div>
              <select
                value={user.role}
                disabled={user.role === "moderator"}
                onChange={(event) => changeRole(user._id, event.target.value)}
              >
                <option value="student">Студент</option>
                <option value="admin">Адмін</option>
                <option value="moderator">Модератор</option>
              </select>
            </article>
          ))}
        </div>
      </section>}
    </section>
  );
}

function BookManagement() {
  const [books, setBooks] = useState([]);
  const [bookSearch, setBookSearch] = useState("");
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    title: "",
    author: "",
    genre: "",
    description: "",
    cover_image_url: "",
  });
  const [message, setMessage] = useState("");
  const load = () =>
    booksApi
      .list()
      .then(({ data }) => setBooks(data))
      .catch(() => setMessage("Не вдалося завантажити книги."));
  useEffect(() => {
    load();
  }, []);
  const startEdit = (book) => {
    setEditing(book._id);
    setForm({
      title: book.title,
      author: book.author,
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
    } catch {
      setMessage("Не вдалося оновити книгу.");
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
  const visibleBooks = books.filter((book) => book.title.toLowerCase().includes(bookSearch.trim().toLowerCase()));
  return (
    <section className="management-section book-management">
      <div className="section-heading">
        <p className="eyebrow">CATALOG</p>
        <h2>Книги на полиці</h2>
        <p>Редагуйте дані або прибирайте застарілі позиції.</p>
      </div>
      <input className="management-search" placeholder="Пошук книг за назвою" value={bookSearch} onChange={(event) => setBookSearch(event.target.value)} />
      {message && <p className="notice">{message}</p>}
      <div className="managed-books">
        {visibleBooks.map((book) =>
          editing === book._id ? (
            <article className="managed-book editing-book" key={book._id}>
              <p className="editing-label">Ви редагуєте книгу</p>
              <div className="proposal-edit-grid">
                <label>Назва<input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
                <label>Автор<input value={form.author} onChange={(event) => setForm({ ...form, author: event.target.value })} /></label>
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
      </div>
    </section>
  );
}

function StaffProposalCard({ proposal, onChange }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    title: proposal.title,
    author: proposal.author,
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
    } catch {
      setMessage("Не вдалося зберегти зміни.");
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
      <BookAdminPanel />
      <BookManagement />
      <StaffProposalInbox />
    </section>
  );
}

export default function App() {
  return <Layout />;
}
