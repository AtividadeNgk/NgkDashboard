// Função para selecionar um bot
function selectBot(botId) {
    window.location.href = '/bot/' + botId + '/select';
}

// Função para mostrar alertas temporários
function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-' + type;
    alertDiv.textContent = message;
    
    document.querySelector('.content').prepend(alertDiv);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}