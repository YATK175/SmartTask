
class RecommendationService:
    """Формує рекомендації для оптимізації виконання завдань."""

    @staticmethod
    def explain_factors(task, features: dict) -> list:
        """
        Формує пояснення контекстних факторів завдання.

        Це прозорий rule-based аналіз характеристик,
        а не локальна атрибуція Random Forest.
        """

        factors = []

        days_left = features["days_until_deadline"]
        duration = features["estimated_duration_hours"]
        active_tasks = features["active_tasks_count"]
        completion_rate = features["on_time_completion_rate"]
        task_age = features["task_age_days"]

        # 1. Дедлайн
        if task.is_overdue():
            factors.append({
                "name": "Дедлайн",
                "value": "Прострочений",
                "level": "HIGH",
                "explanation": (
                    "Термін виконання завдання вже минув."
                )
            })

        elif days_left <= 1:
            factors.append({
                "name": "Дедлайн",
                "value": f"{days_left:.1f} дн.",
                "level": "HIGH",
                "explanation": (
                    "До завершення терміну залишилося дуже мало часу."
                )
            })

        elif days_left <= 3:
            factors.append({
                "name": "Дедлайн",
                "value": f"{days_left:.1f} дн.",
                "level": "MEDIUM",
                "explanation": (
                    "Дедлайн наближається. Варто прискорити виконання."
                )
            })

        else:
            factors.append({
                "name": "Дедлайн",
                "value": f"{days_left:.1f} дн.",
                "level": "LOW",
                "explanation": (
                    "Час до дедлайну поки не є критичним."
                )
            })

        # 2. Співвідношення тривалості та доступного часу.
        # 6 годин на день — умовне проєктне припущення.
        available_hours = max(days_left * 6, 1)

        workload_ratio = duration / available_hours

        if workload_ratio >= 1:
            factors.append({
                "name": "Тривалість роботи",
                "value": f"{duration:.1f} год.",
                "level": "HIGH",
                "explanation": (
                    "Очікувана тривалість роботи велика "
                    "відносно умовно доступного часу."
                )
            })

        elif workload_ratio >= 0.5:
            factors.append({
                "name": "Тривалість роботи",
                "value": f"{duration:.1f} год.",
                "level": "MEDIUM",
                "explanation": (
                    "Для виконання завдання знадобиться "
                    "значна частина доступного часу."
                )
            })

        else:
            factors.append({
                "name": "Тривалість роботи",
                "value": f"{duration:.1f} год.",
                "level": "LOW",
                "explanation": (
                    "Запланована тривалість поки "
                    "виглядає прийнятною."
                )
            })

        # 3. Навантаження користувача.
        if active_tasks >= 8:
            factors.append({
                "name": "Активні завдання",
                "value": str(active_tasks),
                "level": "HIGH",
                "explanation": (
                    "Велика кількість активних завдань "
                    "може ускладнити планування."
                )
            })

        elif active_tasks >= 5:
            factors.append({
                "name": "Активні завдання",
                "value": str(active_tasks),
                "level": "MEDIUM",
                "explanation": (
                    "Поточне навантаження досить високе."
                )
            })

        else:
            factors.append({
                "name": "Активні завдання",
                "value": str(active_tasks),
                "level": "LOW",
                "explanation": (
                    "Кількість інших активних завдань невелика."
                )
            })

        # 4. Історія своєчасного виконання.
        if completion_rate < 0.45:
            factors.append({
                "name": "Своєчасне виконання",
                "value": f"{completion_rate:.0%}",
                "level": "HIGH",
                "explanation": (
                    "Історія показує низьку частку "
                    "вчасно виконаних завдань."
                )
            })

        elif completion_rate < 0.60:
            factors.append({
                "name": "Своєчасне виконання",
                "value": f"{completion_rate:.0%}",
                "level": "MEDIUM",
                "explanation": (
                    "Є можливість покращити дисципліну виконання."
                )
            })

        else:
            factors.append({
                "name": "Своєчасне виконання",
                "value": f"{completion_rate:.0%}",
                "level": "LOW",
                "explanation": (
                    "Історія виконання не показує "
                    "виражених проблем із дедлайнами."
                )
            })

        # 5. Вік завдання.
        if task_age >= 7:
            factors.append({
                "name": "Вік завдання",
                "value": f"{task_age:.1f} дн.",
                "level": "MEDIUM",
                "explanation": (
                    "Завдання існує вже тривалий час. "
                    "Варто перевірити прогрес."
                )
            })

        else:
            factors.append({
                "name": "Вік завдання",
                "value": f"{task_age:.1f} дн.",
                "level": "LOW",
                "explanation": (
                    "Завдання створене відносно недавно."
                )
            })

        return factors

    def generate(self, task, prediction: dict) -> dict:
        """Повертає рекомендації відповідно до ризику завдання."""

        features = prediction["features_snapshot"]

        risk_score = prediction["risk_score"]
        risk_level = prediction["risk_level"]
        is_at_risk = prediction["is_at_risk"]

        days_left = features["days_until_deadline"]
        estimated_hours = features["estimated_duration_hours"]
        active_tasks = features["active_tasks_count"]
        completion_rate = features["on_time_completion_rate"]

        recommendations = []

        if task.is_overdue():
            recommendations.append(
                "Дедлайн уже минув. "
                "Оновіть план виконання та встановіть новий термін."
            )

        elif is_at_risk:
            recommendations.append(
                "Зверніть увагу на це завдання: "
                "модель виявила підвищений сигнал ризику."
            )

        if not task.is_overdue() and days_left <= 1:
            recommendations.append(
                "Дедлайн наближається. "
                "Рекомендуємо розпочати або продовжити роботу сьогодні."
            )

        elif days_left <= 3:
            recommendations.append(
                "До дедлайну залишилося небагато часу. "
                "Розподіліть роботу на короткі етапи."
            )

        if active_tasks >= 8:
            recommendations.append(
                "У вас велика кількість активних завдань. "
                "Рекомендуємо переглянути пріоритети."
            )

        elif active_tasks >= 5:
            recommendations.append(
                "Поточне навантаження досить високе. "
                "Уникайте одночасного виконання багатьох завдань."
            )

        if completion_rate < 0.45:
            recommendations.append(
                "Історія виконання показує низьку частку "
                "своєчасного завершення. Спробуйте встановлювати "
                "проміжні контрольні терміни."
            )

        if (
            estimated_hours > max(days_left * 6, 1)
            and not task.is_overdue()
        ):
            recommendations.append(
                "Очікувана тривалість роботи велика відносно "
                "доступного часу. Розбийте завдання на менші частини."
            )

        if risk_level == "HIGH":
            recommendations.append(
                "Розгляньте можливість тимчасово відкласти "
                "менш важливі завдання."
            )

        if not recommendations:
            recommendations.append(
                "Поточні характеристики завдання не свідчать "
                "про критичні проблеми. Продовжуйте дотримуватися плану."
            )

        if risk_level == "HIGH":
            summary = "Високий рівень ризику."
        elif risk_level == "MEDIUM":
            summary = "Помірний рівень ризику."
        else:
            summary = "Низький рівень ризику."
        contextual_factors = self.explain_factors(
    task,
    features
)

        return {
            "contextual_factors": contextual_factors,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "is_at_risk": is_at_risk,
            "source": prediction["source"],
            "model_version": prediction["model_version"],
            "summary": summary,
            "recommendations": recommendations,
        }
