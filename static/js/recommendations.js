
// Bootstrap form validation
(function () {
    'use strict';
    window.addEventListener('load', function () {
        // Fetch all forms with needs-validation
        var forms = document.getElementsByClassName('needs-validation');
        Array.prototype.filter.call(forms, function (form) {
            form.addEventListener('submit', function (event) {
                if (form.checkValidity() === false) {
                    event.preventDefault();
                    event.stopPropagation();
                }
                form.classList.add('was-validated');
            }, false);
        });
    }, false);
})();

// Real-time input validation for age and time
document.addEventListener('DOMContentLoaded', function () {
    // Diet form age validation
    const dietAgeInput = document.querySelector('#diet-form [name="age"]');
    dietAgeInput.addEventListener('input', function () {
        if (dietAgeInput.value < 1 || dietAgeInput.value > 120) {
            dietAgeInput.classList.add('is-invalid');
        } else {
            dietAgeInput.classList.remove('is-invalid');
        }
    });

    // Workout form age validation
    const workoutAgeInput = document.querySelector('#workout-form [name="age"]');
    workoutAgeInput.addEventListener('input', function () {
        if (workoutAgeInput.value < 1 || workoutAgeInput.value > 120) {
            workoutAgeInput.classList.add('is-invalid');
        } else {
            workoutAgeInput.classList.remove('is-invalid');
        }
    });

    // Workout form time validation
    const timeInput = document.querySelector('#workout-form [name="time"]');
    timeInput.addEventListener('input', function () {
        if (timeInput.value < 10 || timeInput.value > 240) {
            timeInput.classList.add('is-invalid');
        } else {
            timeInput.classList.remove('is-invalid');
        }
    });
});
