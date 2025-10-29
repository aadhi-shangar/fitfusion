
# FitFusion

**FitFusion** is a web-based fitness and health tracking application that enables users to monitor their diet, workouts, and personal health metrics through an intuitive and interactive interface.

---

## Features

* Multi-step health tracking form
* Personalized workout and diet recommendations
* Input validation for height, weight, age, and gender
* Interactive and responsive user interface built with Bootstrap and Tailwind CSS
* (Planned) AI-powered fitness chatbot
* Backend powered by Python Flask

---

## Tech Stack

| Category       | Technologies                                     |
| -------------- | ------------------------------------------------ |
| **Frontend**   | HTML5, CSS3, JavaScript, Bootstrap, Tailwind CSS |
| **Backend**    | Python (Flask)                                   |
| **Database**   | SQLite                                           |
| **Deployment** | (Configurable for local or cloud deployment)     |

---

## Project Structure

```
FitFusion/
│
├── templates/           # HTML Templates (Jinja2)
│   ├── index.html
│   ├── form.html
│   └── result.html
│
├── static/              # Static Files
│   ├── css/
│   └── js/
│
├── app.py               # Main Flask Application
├── requirements.txt     # Python Dependencies
└── README.md
```

---

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/fitfusion.git
cd fitfusion
```

### 2. Create a Virtual Environment (Recommended)

```bash
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
python app.py
```

### 5. Access the Application

Open your browser and navigate to:

```
http://127.0.0.1:5000
```

---

## Future Improvements

* Integration of an AI-powered fitness chatbot
* User authentication and profile management
* Workout history tracking and progress visualization
* Administrative dashboard for managing user data

---

## Contributing

Contributions are welcome!
If you plan to make major changes, please open an issue first to discuss the proposed modifications.
You can also submit a pull request with your improvements or bug fixes.

---

## License

This project is licensed under the **MIT License**.
See the [LICENSE](LICENSE) file for more information.

---

## Author

**Aadhi Shangar M**

---

