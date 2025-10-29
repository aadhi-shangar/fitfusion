import pandas as pd
import numpy as np
from typing import Dict, List, Optional

class DietRecommendationSystem:
    def __init__(self, data_path: str):
        """Initialize the system by loading the dataset."""
        try:
            self.data = pd.read_csv(data_path)
            self.meal_columns = [
                'Recommended_Breakfast', 'Breakfast_Calories',
                'Recommended_Mid-Morning', 'Mid-Morning_Calories',
                'Recommended_Lunch', 'Lunch_Calories',
                'Recommended_Evening_Snack', 'Evening_Snack_Calories',
                'Recommended_Dinner', 'Dinner_Calories',
                'Recommended_Post-Dinner', 'Post-Dinner_Calories'
            ]
            self.validate_data()
        except FileNotFoundError:
            raise FileNotFoundError(f"Dataset file {data_path} not found.")
        except Exception as e:
            raise Exception(f"Error loading dataset: {str(e)}")

    def validate_data(self):
        """Validate that required columns exist in the dataset."""
        required_columns = [
            'Age', 'Gender', 'Goal', 'Diet_Type', 'Allergies',
            'Medical_Conditions', 'Activity_Level'
        ] + self.meal_columns
        missing_columns = [col for col in required_columns if col not in self.data.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

    def normalize_input(self, user_input: Dict) -> Dict:
        """Normalize user inputs to match dataset values."""
        normalized = user_input.copy()
        for key in ['Gender', 'Goal', 'Diet_Type', 'Activity_Level']:
            if key in normalized and normalized[key]:
                normalized[key] = ' '.join(word.capitalize() for word in normalized[key].split())
        if normalized.get('Allergies', '').lower() == 'none':
            normalized['Allergies'] = None
        if normalized.get('Medical_Conditions', '').lower() == 'none':
            normalized['Medical_Conditions'] = None
        return normalized

    def calculate_similarity(self, user_input: Dict, row: pd.Series) -> float:
        """Calculate similarity score between user input and a dataset row."""
        score = 0.0
        max_age_diff = 50
        age_diff = abs(user_input.get('Age', row['Age']) - row['Age'])
        score += 0.2 * (1 - age_diff / max_age_diff)
        if user_input.get('Gender', row['Gender']) == row['Gender']:
            score += 0.2
        if user_input.get('Goal', row['Goal']) == row['Goal']:
            score += 0.3
        if user_input.get('Diet_Type', row['Diet_Type']) == row['Diet_Type']:
            score += 0.2
        if user_input.get('Activity_Level', row['Activity_Level']) == row['Activity_Level']:
            score += 0.1
        return score

    def filter_by_restrictions(self, df: pd.DataFrame, allergies: Optional[str], medical_conditions: Optional[str]) -> pd.DataFrame:
        """Filter dataset based on allergies and medical conditions."""
        filtered_df = df.copy()
        if allergies and allergies.lower() != 'none':
            allergy_list = allergies.split(',')
            for allergy in allergy_list:
                filtered_df = filtered_df[~filtered_df['Allergies'].str.contains(allergy.strip(), case=False, na=False)]
        if medical_conditions and medical_conditions.lower() != 'none':
            condition_list = medical_conditions.split(',')
            for condition in condition_list:
                filtered_df = filtered_df[
                    filtered_df['Medical_Conditions'].str.contains(condition.strip(), case=False, na=False) |
                    (filtered_df['Medical_Conditions'] == 'None')
                ]
        return filtered_df

    def recommend_diet(self, user_input: Dict) -> Optional[Dict]:
        """Recommend a diet plan based on user input."""
        user_input = self.normalize_input(user_input)
        filtered_data = self.filter_by_restrictions(
            self.data,
            user_input.get('Allergies'),
            user_input.get('Medical_Conditions')
        )
        if filtered_data.empty:
            filtered_data = self.data.copy()  # Fallback to avoid empty results
        scores = filtered_data.apply(lambda row: self.calculate_similarity(user_input, row), axis=1)
        best_match_idx = scores.idxmax()
        best_match = filtered_data.loc[best_match_idx]
        meal_plan = {
            'Breakfast': {
                'Meal': best_match['Recommended_Breakfast'],
                'Calories': int(best_match['Breakfast_Calories'])
            },
            'Mid-Morning': {
                'Meal': best_match['Recommended_Mid-Morning'],
                'Calories': int(best_match['Mid-Morning_Calories'])
            },
            'Lunch': {
                'Meal': best_match['Recommended_Lunch'],
                'Calories': int(best_match['Lunch_Calories'])
            },
            'Evening Snack': {
                'Meal': best_match['Recommended_Evening_Snack'],
                'Calories': int(best_match['Evening_Snack_Calories'])
            },
            'Dinner': {
                'Meal': best_match['Recommended_Dinner'],
                'Calories': int(best_match['Dinner_Calories'])
            },
            'Post-Dinner': {
                'Meal': best_match['Recommended_Post-Dinner'],
                'Calories': int(best_match['Post-Dinner_Calories']) if pd.notna(best_match['Recommended_Post-Dinner']) else 0
            },
            'Total Calories': int(best_match[self.meal_columns[1::2]].sum())
        }
        return meal_plan