document.getElementById('chatbot-form').addEventListener('submit', async function(event) {
    event.preventDefault();
    const input = document.getElementById('chatbot-input').value;
    const messagesDiv = document.getElementById('chatbot-messages');
    messagesDiv.innerHTML += `<p><strong>You:</strong> ${input}</p>`;
    messagesDiv.innerHTML +- `<p><em>Loading...</em></p>`;
    try {
        const response = await fetch('/api/chatbot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: input })
        });
        const data = await response.json();
        messagesDiv.innerHTML = messagesDiv.innerHTML.replace('<p><em>Loading...</em></p>', '');
        messagesDiv.innerHTML += `<p><strong>FitBot:</strong> ${data.response}</p>`;
    } catch (error) {
        messagesDiv.innerHTML = messagesDiv.innerHTML.replace('<p><em>Loading...</em></p>', '');
        messagesDiv.innerHTML += `<p><strong>FitBot:</strong> Sorry, I couldn't process that. Try again!</p>`;
    }
    document.getElementById('chatbot-input').value = '';
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
});
