document.addEventListener('DOMContentLoaded', () => {
    const themeToggleBtn = document.getElementById('theme-toggle');
    const body = document.body;

    const applySavedTheme = () => {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'light') {
            body.classList.add('light-theme');
        }
    };

    const handleThemeToggle = () => {
        body.classList.toggle('light-theme');

        if (body.classList.contains('light-theme')) {
            localStorage.setItem('theme', 'light');
        } else {
            localStorage.setItem('theme', 'dark');
        }
    };

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', handleThemeToggle);
    }
    
    applySavedTheme();

    const updateAuthButton = () => {
        const authButton = document.getElementById('authButton');
        const user = JSON.parse(localStorage.getItem('user'));
        
        if (authButton && user) {
            authButton.textContent = user.name;
            authButton.href = '#';
            authButton.addEventListener('click', (e) => {
                e.preventDefault();
                if (confirm('Do you want to logout?')) {
                    fetch('/api/logout', { method: 'POST' })
                        .then(() => {
                            localStorage.removeItem('user');
                            window.location.href = '/';
                        });
                }
            });
        }
    };

    updateAuthButton();

    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', (event) => {
            // Only prevent default for links that don't have a real href
            if (link.getAttribute('href') === '#') {
                event.preventDefault();
            }
            // Update active class
            document.querySelector('.nav-link.active')?.classList.remove('active');
            event.currentTarget.classList.add('active');
        });
    });

    const header = document.querySelector('.main-header');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 10) {
            header.style.boxShadow = "0 8px 32px rgba(0, 0, 0, 0.12)";
        } else {
            header.style.boxShadow = "none";
        }
    });
});
