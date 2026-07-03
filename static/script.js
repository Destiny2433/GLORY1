// ========================================================
// GLORY MODAL SYSTEM — replaces all browser alert() calls
// ========================================================
(function() {
    // Inject modal HTML if not already present
    function ensureModal() {
        if (document.getElementById('glory-modal-overlay')) return;
        const overlay = document.createElement('div');
        overlay.id = 'glory-modal-overlay';
        overlay.style.cssText = 'display:none;position:fixed;inset:0;background:rgba(0,0,0,0.75);z-index:99999;backdrop-filter:blur(6px);align-items:center;justify-content:center;';
        overlay.innerHTML = `
            <div id="glory-modal-box" style="
                background:linear-gradient(135deg,#1a0a2e 0%,#0d1b2a 100%);
                border:1px solid rgba(255,215,0,0.4);
                border-radius:20px;
                padding:40px 36px;
                max-width:440px;
                width:90%;
                text-align:center;
                box-shadow:0 20px 60px rgba(0,0,0,0.6);
                animation:gloryModalPop 0.3s cubic-bezier(0.34,1.56,0.64,1);
            ">
                <div id="glory-modal-icon" style="font-size:3rem;margin-bottom:16px;"></div>
                <h3 id="glory-modal-title" style="color:#FFD700;font-family:'Righteous',cursive;font-size:1.5rem;margin:0 0 10px;"></h3>
                <p id="glory-modal-message" style="color:rgba(255,255,255,0.78);line-height:1.65;margin:0 0 28px;font-size:1rem;"></p>
                <button id="glory-modal-close" style="
                    background:linear-gradient(135deg,#FFD700,#FFA500);
                    color:#000;
                    border:none;
                    padding:12px 36px;
                    border-radius:10px;
                    font-weight:700;
                    font-size:1rem;
                    cursor:pointer;
                    font-family:'Righteous',cursive;
                    letter-spacing:0.04em;
                    transition:transform 0.2s,box-shadow 0.2s;
                ">OK</button>
            </div>
        `;
        // Inject animation keyframe
        const styleTag = document.createElement('style');
        styleTag.textContent = `
            @keyframes gloryModalPop {
                from { transform: scale(0.7); opacity: 0; }
                to   { transform: scale(1);   opacity: 1; }
            }
            #glory-modal-close:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(255,215,0,0.45);
            }
        `;
        document.head.appendChild(styleTag);
        document.body.appendChild(overlay);

        // Close on button or overlay click
        overlay.querySelector('#glory-modal-close').addEventListener('click', closeGloryModal);
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) closeGloryModal();
        });
        // Close on Escape
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeGloryModal();
        });
    }

    function closeGloryModal() {
        const overlay = document.getElementById('glory-modal-overlay');
        if (overlay) overlay.style.display = 'none';
    }

    // Public function — call gloryAlert(message, title, icon) anywhere
    window.gloryAlert = function(message, title, icon) {
        ensureModal();
        const overlay = document.getElementById('glory-modal-overlay');
        document.getElementById('glory-modal-icon').textContent    = icon    || '✨';
        document.getElementById('glory-modal-title').textContent   = title   || 'Notice';
        document.getElementById('glory-modal-message').textContent = message || '';
        overlay.style.display = 'flex';
    };
})();

// Intersection Observer for fade-in animations

const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
        }
    });
}, observerOptions);

document.querySelectorAll('.fade-in').forEach(el => {
    observer.observe(el);
});

// Particle effect for hero
function createParticles() {
    const hero = document.querySelector('.hero');
    if (hero) {
        for (let i = 0; i < 50; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle';
            particle.style.left = Math.random() * 100 + '%';
            particle.style.animationDelay = Math.random() * 10 + 's';
            particle.style.animationDuration = (Math.random() * 5 + 5) + 's';
            hero.appendChild(particle);
        }
    }
}

createParticles();

// Scroll-triggered animations
window.addEventListener('scroll', () => {
    const hero = document.querySelector('.hero');
    if (hero) {
        const scrolled = window.pageYOffset;
        const rate = scrolled * -0.5;
        hero.style.transform = `translateY(${rate}px)`;
    }
});

// Typing effect for subtitle
const subtitle = document.querySelector('.hero-subtitle');
if (subtitle) {
    const text = subtitle.textContent;
    subtitle.textContent = '';
    let i = 0;

    function typeWriter() {
        if (i < text.length) {
            subtitle.textContent += text.charAt(i);
            i++;
            setTimeout(typeWriter, 100);
        }
    }

    setTimeout(typeWriter, 2000);
}

// Hover effects for minister cards
document.querySelectorAll('.minister-card').forEach(card => {
    card.addEventListener('mouseenter', () => {
        card.style.animationPlayState = 'paused';
    });
    card.addEventListener('mouseleave', () => {
        card.style.animationPlayState = 'running';
    });
});

// Gallery lightbox effect
const galleryImages = Array.from(document.querySelectorAll('.gallery-item img'));
let currentImageIndex = 0;

document.querySelectorAll('.gallery-item img').forEach((img, index) => {
    img.addEventListener('click', () => {
        currentImageIndex = index;
        showLightbox();
    });
});

function showLightbox() {
    const lightbox = document.createElement('div');
    lightbox.className = 'lightbox';
    lightbox.innerHTML = `
        <div class="lightbox-top">
            <span class="counter">${currentImageIndex + 1} / ${galleryImages.length}</span>
            <span class="close">&times;</span>
        </div>
        <span class="prev">&#10094;</span>
        <span class="next">&#10095;</span>
        <img src="${galleryImages[currentImageIndex].src}" alt="${galleryImages[currentImageIndex].alt || 'Gallery Image'}">
    `;
    document.body.appendChild(lightbox);

    const img = lightbox.querySelector('img');
    const prevBtn = lightbox.querySelector('.prev');
    const nextBtn = lightbox.querySelector('.next');
    const closeBtn = lightbox.querySelector('.close');

    function updateImage() {
        img.src = galleryImages[currentImageIndex].src;
        img.alt = galleryImages[currentImageIndex].alt || 'Gallery Image';
        const counter = lightbox.querySelector('.counter');
        if (counter) counter.textContent = `${currentImageIndex + 1} / ${galleryImages.length}`;
    }

    prevBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        currentImageIndex = (currentImageIndex - 1 + galleryImages.length) % galleryImages.length;
        updateImage();
    });

    nextBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        currentImageIndex = (currentImageIndex + 1) % galleryImages.length;
        updateImage();
    });

    closeBtn.addEventListener('click', () => {
        lightbox.remove();
    });

    lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) {
            lightbox.remove();
        }
    });

    // Keyboard navigation
    document.addEventListener('keydown', function keyHandler(e) {
        if (lightbox.parentNode) {
            if (e.key === 'ArrowLeft') {
                prevBtn.click();
            } else if (e.key === 'ArrowRight') {
                nextBtn.click();
            } else if (e.key === 'Escape') {
                lightbox.remove();
                document.removeEventListener('keydown', keyHandler);
            }
        }
    });
}

// Add CSS for particles and lightbox
const style = document.createElement('style');
style.textContent = `
    .particle {
        position: absolute;
        width: 10px;
        height: 10px;
        background: rgba(255, 215, 0, 0.8);
        border-radius: 50%;
        animation: floatParticle 10s linear infinite;
        pointer-events: none;
    }

    @keyframes floatParticle {
        0% { transform: translateY(100vh) rotate(0deg); opacity: 1; }
        100% { transform: translateY(-100px) rotate(360deg); opacity: 0; }
    }

    .lightbox {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.95);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        cursor: pointer;
        flex-direction: column;
    }

    .lightbox img {
        max-width: 100%;
        max-height: 80vh;
        border-radius: 10px;
        object-fit: contain;
    }

    .lightbox-top {
        position: absolute;
        top: 20px;
        left: 0;
        width: 100%;
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0 30px;
        box-sizing: border-box;
        z-index: 1001;
    }

    .lightbox .counter {
        color: #fff;
        font-size: 1.2rem;
        font-family: 'Orbitron', monospace;
        background: rgba(0, 0, 0, 0.5);
        padding: 5px 15px;
        border-radius: 20px;
    }

    .lightbox .close {
        color: #fff;
        font-size: 40px;
        font-weight: bold;
        cursor: pointer;
        transition: color 0.3s;
    }
    
    .lightbox .close:hover { color: #FFD700; }

    .lightbox .prev, .lightbox .next {
        position: absolute;
        top: 50%;
        transform: translateY(-50%);
        color: #fff;
        font-size: 40px;
        font-weight: bold;
        cursor: pointer;
        padding: 15px;
        user-select: none;
        z-index: 1001;
        transition: all 0.3s ease;
        background: rgba(0, 0, 0, 0.3);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 60px;
        height: 60px;
    }

    .lightbox .prev { left: 20px; }
    .lightbox .next { right: 20px; }

    .lightbox .prev:hover, .lightbox .next:hover {
        color: #FFD700;
        background: rgba(0, 0, 0, 0.8);
    }

    @media (max-width: 768px) {
        .lightbox .prev, .lightbox .next {
            font-size: 25px;
            width: 40px;
            height: 40px;
            padding: 5px;
        }
        .lightbox .prev { left: 10px; }
        .lightbox .next { right: 10px; }
        .lightbox img { max-width: 95%; max-height: 70vh; }
        .lightbox-top { padding: 0 15px; top: 10px; }
    }
`;
document.head.appendChild(style);

// Slideshow logic
let currentSlide = 0;
const slides = document.querySelectorAll('.slide');
const dots = document.querySelectorAll('.dot');
const video = document.getElementById('hero-video');

if (slides.length > 0) {
    function showSlide(index) {
        slides.forEach(slide => slide.classList.remove('active'));
        dots.forEach(dot => dot.classList.remove('active'));
        slides[index].classList.add('active');
        dots[index].classList.add('active');
        currentSlide = index;
    }

    function nextSlide() {
        currentSlide = (currentSlide + 1) % slides.length;
        showSlide(currentSlide);
    }

    dots.forEach((dot, index) => {
        dot.addEventListener('click', () => {
            showSlide(index);
        });
    });

    // Auto-play slideshow every 3 seconds
    setInterval(nextSlide, 25000);
}

// Crazy animation for social icons
document.querySelectorAll('.social-bar a').forEach(icon => {
    icon.addEventListener('mouseenter', () => {
        icon.style.animation = 'none';
        setTimeout(() => {
            icon.style.animation = 'bounce 1s ease-in-out';
        }, 10);
    });
});

// Add bounce keyframe
const bounceStyle = document.createElement('style');
bounceStyle.textContent = `
    @keyframes bounce {
        0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
        40% { transform: translateY(-30px); }
        60% { transform: translateY(-15px); }
    }
`;
document.head.appendChild(bounceStyle);

// Back to Top button functionality
const backToTopBtn = document.getElementById('back-to-top');

if (backToTopBtn) {
    window.addEventListener('scroll', () => {
        if (window.pageYOffset > 300) {
            backToTopBtn.classList.add('show');
        } else {
            backToTopBtn.classList.remove('show');
        }
    });

    backToTopBtn.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}





// Navigation Menu Toggle
const menuToggle = document.querySelector('.menu-toggle');
const navMenu = document.querySelector('.nav-menu');
if (menuToggle && navMenu) {
    menuToggle.addEventListener('click', () => {
        navMenu.classList.toggle('active');
        menuToggle.classList.toggle('active');
    });

    // Close menu when a link is clicked
    const navLinks = document.querySelectorAll('.nav-menu li a');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            navMenu.classList.remove('active');
            menuToggle.classList.remove('active');
        });
    });
}

// Newsletter signup
document.addEventListener('DOMContentLoaded', function() {


    // Volunteer form team selection
    const teamSelect = document.getElementById('team');
    const mediaFields = document.getElementById('media-fields');
    const praiseFields = document.getElementById('praise-fields');
    if (teamSelect) {
        teamSelect.addEventListener('change', function() {
            const selectedTeam = this.value;

            // Hide all team-specific fields
            if (mediaFields) mediaFields.style.display = 'none';
            if (praiseFields) praiseFields.style.display = 'none';

            // Show the selected team's fields
            if (selectedTeam === 'media' && mediaFields) {
                mediaFields.style.display = 'block';
            } else if (selectedTeam === 'praiseteam' && praiseFields) {
                praiseFields.style.display = 'block';
            }
        });
    }
});
