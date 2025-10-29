$(document).ready(function() {
    // Add Todo
    $('#add-todo').submit(function(e) {
        e.preventDefault();
        let task = $('#todo-task').val();
        if (task) {
            $.ajax({
                url: '/api/todos',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ task: task }),
                success: function(data) {
                    $('#todo-list').append(
                        `<li><input type="checkbox" onchange="updateTodo(${data.id}, this.checked)"> ${data.task} ` +
                        `<button onclick="deleteTodo(${data.id})">Delete</button></li>`
                    );
                    $('#todo-task').val('');
                },
                error: function(xhr) {
                    alert('Error adding todo: ' + xhr.responseJSON.error);
                }
            });
        }
    });

    // Update Water Intake
    $('#water-form').submit(function(e) {
        e.preventDefault();
        let value = parseFloat($('#water-intake').val());
        $.ajax({
            url: '/api/update_water',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ action: 'set', value: value }),
            success: function(data) {
                $('#water-intake-display').text(data.intake.toFixed(1));
            },
            error: function(xhr) {
                alert('Error updating water intake: ' + xhr.responseJSON.error);
            }
        });
    });

    // Update Steps
    $('#steps-form').submit(function(e) {
        e.preventDefault();
        let value = parseInt($('#steps-count').val());
        $.ajax({
            url: '/api/update_steps',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ action: 'set', value: value }),
            success: function(data) {
                $('#steps-count-display').text(data.count);
            },
            error: function(xhr) {
                alert('Error updating steps: ' + xhr.responseJSON.error);
            }
        });
    });

    // Chatbot Interaction
    $('#chatbot-form').submit(function(e) {
        e.preventDefault();
        let message = $('#chatbot-input').val();
        if (message) {
            $('#chatbot-messages').append(`<p><strong>You:</strong> ${message}</p>`);
            $.ajax({
                url: '/api/chatbot',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ message: message }),
                success: function(data) {
                    $('#chatbot-messages').append(`<p><strong>Bot:</strong> ${data.response}</p>`);
                    $('#chatbot-input').val('');
                    $('#chatbot-messages').scrollTop($('#chatbot-messages')[0].scrollHeight);
                },
                error: function(xhr) {
                    $('#chatbot-messages').append(`<p><strong>Bot:</strong> Error: ${xhr.responseJSON.response}</p>`);
                }
            });
        }
    });
});

function updateTodo(id, completed) {
    $.ajax({
        url: '/api/todos',
        type: 'PUT',
        contentType: 'application/json',
        data: JSON.stringify({ id: id, completed: completed }),
        error: function(xhr) {
            alert('Error updating todo: ' + xhr.responseJSON.error);
        }
    });
}

function deleteTodo(id) {
    $.ajax({
        url: '/api/todos',
        type: 'DELETE',
        contentType: 'application/json',
        data: JSON.stringify({ id: id }),
        success: function() {
            $(`#todo-list li:contains(${id})`).remove();
        },
        error: function(xhr) {
            alert('Error deleting todo: ' + xhr.responseJSON.error);
        }
    });
}
