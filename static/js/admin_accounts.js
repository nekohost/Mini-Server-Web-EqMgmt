(() => {
    const dialog = document.getElementById('createUserDialog');
    const form = document.getElementById('createUserForm');
    const fields = form.querySelector('fieldset');
    const submit = form.querySelector('[type="submit"]');
    const error = document.getElementById('createUserError');
    const result = document.getElementById('createUserResult');

    document.getElementById('openCreateUser').addEventListener('click', () => {
        result.textContent = '';
        dialog.showModal();
    });
    document.getElementById('cancelCreateUser').addEventListener('click', () => dialog.close());
    dialog.addEventListener('cancel', event => {
        if (fields.disabled) event.preventDefault();
    });
    dialog.addEventListener('close', () => {
        form.reset();
        error.textContent = '';
    });

    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (fields.disabled || !dialog.open) return;
        const payload = Object.fromEntries(new FormData(form));
        fields.disabled = true;
        submit.textContent = '생성 중…';
        error.textContent = '';
        window.showGlobalLoading('계정을 생성하고 있습니다…');
        try {
            const response = await fetch(form.action, {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.getCSRFToken()},
                signal: window.AbortSignal?.timeout?.(30000),
                body: JSON.stringify(payload)
            });
            const data = await response.json();
            if (!response.ok || !data.success) {
                error.textContent = data.message || data.error || '계정을 생성하지 못했습니다.';
                return;
            }
            dialog.close();
            result.textContent = data.message;
            if (!await fetchUsers()) result.textContent += ' 사용자 목록을 새로고침해 주세요.';
        } catch {
            error.textContent = '생성 결과를 확인할 수 없습니다. 사용자 목록을 새로고침한 뒤 다시 시도해 주세요.';
        } finally {
            fields.disabled = false;
            submit.textContent = '계정 생성';
            window.hideGlobalLoading();
        }
    });
})();
