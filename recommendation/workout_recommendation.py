import pandas as pd
import numpy as np
from typing import Dict, Optional

class WorkoutRecommendationSystem:
    def __init__(self, data_path: str):
        """Initialize the system by loading the workout dataset."""
        try:
            self.data = pd.read_csv(data_path)
            self.validate_data()
        except FileNotFoundError:
            raise FileNotFoundError(f"Dataset file {data_path} not found.")
        except Exception as e:
            raise Exception(f"Error loading dataset: {str(e)}")

    def validate_data(self):
        """Validate that required columns exist in the dataset."""
        required_columns = ['Age', 'Gender', 'Fitness_Level', 'Goal', 'Workout_Time_per_day_mins', 'Workout_Preference']
        missing_columns = [col for col in required_columns if col not in self.data.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

    def normalize_input(self, user_input: Dict) -> Dict:
        """Normalize user inputs to match dataset values."""
        normalized = user_input.copy()
        for key in ['Gender', 'Fitness_Level', 'Goal', 'Workout_Preference']:
            if key in normalized and normalized[key]:
                normalized[key] = ' '.join(word.capitalize() for word in normalized[key].split())
        return normalized

    def calculate_similarity(self, user_input: Dict, row: pd.Series) -> float:
        """Calculate similarity score between user input and a dataset row."""
        score = 0.0
        max_age_diff = 50
        age_diff = abs(user_input.get('Age', row['Age']) - row['Age'])
        score += 0.2 * (1 - age_diff / max_age_diff)
        if user_input.get('Gender', row['Gender']) == row['Gender']:
            score += 0.2
        if user_input.get('Fitness_Level', row['Fitness_Level']) == row['Fitness_Level']:
            score += 0.3
        if user_input.get('Goal', row['Goal']) == row['Goal']:
            score += 0.2
        if user_input.get('Workout_Preference', row['Workout_Preference']) == row['Workout_Preference']:
            score += 0.1
        time_diff = abs(user_input.get('Workout_Time_per_day_mins', row['Workout_Time_per_day_mins']) - row['Workout_Time_per_day_mins'])
        max_time_diff = 120
        score += 0.2 * (1 - min(time_diff / max_time_diff, 1))
        return score

    def filter_by_restrictions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter dataset based on any potential restrictions (e.g., injuries could be added)."""
        return df.copy()  # Placeholder; extend with injury or other filters if needed

    def recommend_workout(self, user_input: Dict) -> Optional[Dict]:
        """Recommend a workout plan based on user input."""
        user_input = self.normalize_input(user_input)
        filtered_data = self.filter_by_restrictions(self.data)
        if filtered_data.empty:
            filtered_data = self.data.copy()  # Fallback to avoid empty results
        scores = filtered_data.apply(lambda row: self.calculate_similarity(user_input, row), axis=1)
        best_match_idx = scores.idxmax()
        best_match = filtered_data.loc[best_match_idx]
        workout_plan = {
            'Workout_Type': best_match['Recommended_Workout'],
            'Exercises': best_match['Workout_Exercises'].split(', '),
            'Duration': int(best_match['Workout_Time_per_day_mins'])
        }
        return workout_plan

# Example usage
if __name__ == "__main__":
    # Initialize with your dataset path
    recommender = WorkoutRecommendationSystem("workout_dataset.csv")
    # Sample user input
    user_input = {
        'Age': 30,
        'Gender': 'Male',
        'Fitness_Level': 'Intermediate',
        'Goal': 'Endurance',
        'Workout_Time_per_day_mins': 60,
        'Workout_Preference': 'Home'
    }
    plan = recommender.recommend_workout(user_input)
    print("Recommended Workout Plan:")
    print(f"Type: {plan['Workout_Type']}")
    print(f"Exercises: {plan['Exercises']}")
    print(f"Duration: {plan['Duration']} minutes")