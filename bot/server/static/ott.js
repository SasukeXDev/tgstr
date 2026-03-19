(function () {
    function openModal(id) {
        document.getElementById(id)?.classList.add('is-open');
    }

    function closeModal(id) {
        document.getElementById(id)?.classList.remove('is-open');
    }

    function resetModalState() {
        document.querySelectorAll('.ott-modal.is-open').forEach((modal) => {
            modal.classList.remove('is-open');
        });
    }

    function bindModalDismiss() {
        document.querySelectorAll('.ott-modal').forEach((modal) => {
            modal.addEventListener('click', (event) => {
                if (event.target === modal) {
                    modal.classList.remove('is-open');
                }
            });
        });
    }

    function rememberChannel(id, title) {
        localStorage.setItem('selectedChannelId', id || '');
        localStorage.setItem('selectedChannelTitle', title || '');
        sessionStorage.setItem('selectedChannelId', id || '');
        sessionStorage.setItem('selectedChannelTitle', title || '');
    }

    function getRememberedChannelTitle() {
        return localStorage.getItem('selectedChannelTitle') || sessionStorage.getItem('selectedChannelTitle') || '';
    }

    function syncSelectedLabel(title) {
        const label = document.getElementById('ottSelectedLabel');
        if (label && title) {
            label.textContent = title;
        }
    }

    function bindChannelCards() {
        document.querySelectorAll('.channel-card-link').forEach((link) => {
            link.addEventListener('click', () => {
                rememberChannel(link.dataset.channelId || '', link.dataset.channelTitle || '');
            });
        });
    }

    window.openModal = openModal;
    window.closeModal = closeModal;
    window.OttApp = {
        bindChannelCards,
        bindModalDismiss,
        resetModalState,
        getRememberedChannelTitle,
        rememberChannel,
        syncSelectedLabel,
    };

    document.addEventListener('DOMContentLoaded', () => {
        resetModalState();
        bindModalDismiss();
        syncSelectedLabel(getRememberedChannelTitle());
    });

    window.addEventListener('pageshow', () => {
        resetModalState();
    });
})();
