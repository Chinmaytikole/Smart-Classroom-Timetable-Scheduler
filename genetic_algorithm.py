# genetic_algorithm.py
import random
import numpy as np
from copy import deepcopy

class GeneticTimetable:
    def __init__(self, subjects, faculty, classrooms, batches, constraints):
        self.subjects = subjects
        self.faculty = faculty
        self.classrooms = classrooms
        self.batches = batches
        self.constraints = constraints
        
        # Initialize mappings
        self.subject_map = {s['id']: s for s in subjects}
        self.faculty_map = {f['id']: f for f in faculty}
        self.classroom_map = {c['id']: c for c in classrooms}
        self.batch_map = {b['id']: b for b in batches}
        
        # Initialize parameters
        self.days = constraints.get('days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'])
        self.time_slots = constraints.get('time_slots', ['9:00-10:00', '10:00-11:00', '11:00-12:00', '12:00-1:00', '1:00-2:00', '2:00-3:00', '3:00-4:00', '4:00-5:00'])
        self.lunch_break = constraints.get('lunch_break', '12:00-1:00')
        self.max_classes_per_day = constraints.get('max_classes_per_day', 6)
        self.max_hours_per_faculty = constraints.get('max_hours_per_faculty', 8)
        
    def initialize_population(self, size):
        population = []
        for _ in range(size):
            timetable = {}
            for batch in self.batches:
                batch_id = batch['id']
                timetable[batch_id] = {}
                for day in self.days:
                    timetable[batch_id][day] = {}
                    for time_slot in self.time_slots:
                        # Skip lunch break
                        if time_slot == self.lunch_break:
                            timetable[batch_id][day][time_slot] = None
                            continue
                            
                        # Randomly assign a subject, faculty, and classroom
                        subject = random.choice(self.subjects)
                        faculty_for_subject = self.get_faculty_for_subject(subject['id'])
                        
                        if faculty_for_subject:
                            classroom = self.get_available_classroom(subject['subject_type'])
                            timetable[batch_id][day][time_slot] = {
                                'subject_id': subject['id'],
                                'faculty_id': faculty_for_subject['id'],
                                'classroom_id': classroom['id'] if classroom else None
                            }
                        else:
                            timetable[batch_id][day][time_slot] = None
            population.append(timetable)
        return population
    
    def get_faculty_for_subject(self, subject_id):
        # Find faculty who can teach this subject
        eligible_faculty = [f for f in self.faculty if self.can_teach_subject(f, subject_id)]
        return random.choice(eligible_faculty) if eligible_faculty else None
    
    def can_teach_subject(self, faculty, subject_id):
        # This is a simplified version - in a real system, you'd have a mapping
        # between faculty and subjects they can teach
        # For now, we'll assume faculty can teach any subject in their department
        subject = self.subject_map.get(subject_id)
        if subject and faculty['department_id'] == subject['department_id']:
            return True
        return False
    
    def get_available_classroom(self, subject_type):
        # Filter classrooms based on subject type
        if subject_type == 'LAB':
            labs = [c for c in self.classrooms if c['type'] == 'LAB']
            return random.choice(labs) if labs else None
        else:
            classrooms = [c for c in self.classrooms if c['type'] == 'CLASSROOM']
            return random.choice(classrooms) if classrooms else None
    
    def calculate_fitness(self, timetable):
        fitness_score = 1000  # Start with perfect score
        
        # Check for faculty conflicts
        faculty_conflicts = self.check_faculty_conflicts(timetable)
        fitness_score -= faculty_conflicts * 50
        
        # Check for classroom conflicts
        classroom_conflicts = self.check_classroom_conflicts(timetable)
        fitness_score -= classroom_conflicts * 50
        
        # Check for workload violations
        workload_violations = self.check_workload_violations(timetable)
        fitness_score -= workload_violations * 30
        
        # Check for time preference violations
        time_preference_violations = self.check_time_preferences(timetable)
        fitness_score -= time_preference_violations * 20
        
        # Check for consecutive class violations
        consecutive_class_violations = self.check_consecutive_classes(timetable)
        fitness_score -= consecutive_class_violations * 25
        
        # Check for lunch break violations
        lunch_break_violations = self.check_lunch_breaks(timetable)
        fitness_score -= lunch_break_violations * 15
        
        return max(0, fitness_score)
    
    def check_faculty_conflicts(self, timetable):
        conflicts = 0
        faculty_schedule = {}
        
        for batch_id, schedule in timetable.items():
            for day, time_slots in schedule.items():
                for time_slot, slot_data in time_slots.items():
                    if slot_data and slot_data['faculty_id']:
                        faculty_id = slot_data['faculty_id']
                        key = (faculty_id, day, time_slot)
                        
                        if key in faculty_schedule:
                            conflicts += 1
                        else:
                            faculty_schedule[key] = True
        return conflicts
    
    def check_classroom_conflicts(self, timetable):
        conflicts = 0
        classroom_schedule = {}
        
        for batch_id, schedule in timetable.items():
            for day, time_slots in schedule.items():
                for time_slot, slot_data in time_slots.items():
                    if slot_data and slot_data['classroom_id']:
                        classroom_id = slot_data['classroom_id']
                        key = (classroom_id, day, time_slot)
                        
                        if key in classroom_schedule:
                            conflicts += 1
                        else:
                            classroom_schedule[key] = True
        return conflicts
    
    def check_workload_violations(self, timetable):
        violations = 0
        faculty_hours = {f['id']: 0 for f in self.faculty}
        
        for batch_id, schedule in timetable.items():
            for day, time_slots in schedule.items():
                for time_slot, slot_data in time_slots.items():
                    if slot_data and slot_data['faculty_id']:
                        faculty_id = slot_data['faculty_id']
                        faculty_hours[faculty_id] += 1
        
        for faculty_id, hours in faculty_hours.items():
            faculty = self.faculty_map.get(faculty_id)
            if faculty and hours > faculty.get('max_hours_per_day', self.max_hours_per_faculty) * len(self.days):
                violations += 1
                
        return violations
    
    def check_time_preferences(self, timetable):
        violations = 0
        # This would check against faculty time preferences
        # For now, we'll return 0 as we don't have preference data
        return violations
    
    def check_consecutive_classes(self, timetable):
        violations = 0
        for batch_id, schedule in timetable.items():
            for day, time_slots in schedule.items():
                consecutive_count = 0
                for time_slot in self.time_slots:
                    if time_slot == self.lunch_break:
                        consecutive_count = 0
                        continue
                    
                    if schedule[day].get(time_slot):
                        consecutive_count += 1
                        if consecutive_count > 3:  # More than 3 consecutive classes
                            violations += 1
                    else:
                        consecutive_count = 0
        return violations
    
    def check_lunch_breaks(self, timetable):
        violations = 0
        for batch_id, schedule in timetable.items():
            for day, time_slots in schedule.items():
                if time_slots.get(self.lunch_break):  # If there's a class during lunch break
                    violations += 1
        return violations
    
    def crossover(self, parent1, parent2):
        # Single-point crossover
        child = deepcopy(parent1)
        crossover_point = random.randint(1, len(self.days) - 1)
        crossover_days = self.days[crossover_point:]
        
        for batch_id in parent2:
            if batch_id not in child:
                child[batch_id] = {}
                
            for day in crossover_days:
                if day in parent2[batch_id]:
                    child[batch_id][day] = deepcopy(parent2[batch_id][day])
                    
        return child
    
    def mutate(self, timetable):
        mutated = deepcopy(timetable)
        batch_id = random.choice(list(mutated.keys()))
        day = random.choice(self.days)
        time_slot = random.choice([ts for ts in self.time_slots if ts != self.lunch_break])
        
        if random.random() < 0.5:  # 50% chance to change subject
            subject = random.choice(self.subjects)
            faculty_for_subject = self.get_faculty_for_subject(subject['id'])
            
            if faculty_for_subject:
                classroom = self.get_available_classroom(subject['subject_type'])
                mutated[batch_id][day][time_slot] = {
                    'subject_id': subject['id'],
                    'faculty_id': faculty_for_subject['id'],
                    'classroom_id': classroom['id'] if classroom else None
                }
        else:  # 50% chance to clear the slot
            mutated[batch_id][day][time_slot] = None
            
        return mutated
    
    def run(self, population_size=100, generations=500, mutation_rate=0.1):
        population = self.initialize_population(population_size)
        best_fitness = -1
        best_timetable = None
        
        for generation in range(generations):
            # Evaluate fitness
            fitness_scores = [self.calculate_fitness(timetable) for timetable in population]
            
            # Find best timetable
            max_fitness = max(fitness_scores)
            if max_fitness > best_fitness:
                best_fitness = max_fitness
                best_timetable = population[fitness_scores.index(max_fitness)]
                
            # Select parents (tournament selection)
            selected_parents = []
            for _ in range(population_size):
                tournament_size = 3
                tournament = random.sample(list(zip(population, fitness_scores)), tournament_size)
                winner = max(tournament, key=lambda x: x[1])[0]
                selected_parents.append(winner)
                
            # Create new generation
            new_population = []
            for i in range(0, population_size, 2):
                parent1 = selected_parents[i]
                parent2 = selected_parents[(i + 1) % population_size]
                
                # Crossover
                child1 = self.crossover(parent1, parent2)
                child2 = self.crossover(parent2, parent1)
                
                # Mutation
                if random.random() < mutation_rate:
                    child1 = self.mutate(child1)
                if random.random() < mutation_rate:
                    child2 = self.mutate(child2)
                    
                new_population.extend([child1, child2])
                
            population = new_population[:population_size]
            
            # Print progress
            if generation % 50 == 0:
                print(f"Generation {generation}: Best Fitness = {best_fitness}")
                
        return best_timetable, best_fitness

class EnhancedGeneticTimetable(GeneticTimetable):
    def __init__(self, subjects, faculty, classrooms, batches, constraints):
        super().__init__(subjects, faculty, classrooms, batches, constraints)
        self.population_size = 200
        self.generations = 1000
        self.mutation_rate = 0.15
        self.crossover_rate = 0.85
        self.elitism_rate = 0.1  # Keep best 10% in each generation
        
    def calculate_fitness(self, timetable):
        fitness_score = 1000  # Start with perfect score
        
        # Weight different constraint violations
        faculty_conflicts = self.check_faculty_conflicts(timetable) * 50
        classroom_conflicts = self.check_classroom_conflicts(timetable) * 50
        workload_violations = self.check_workload_violations(timetable) * 30
        time_preference_violations = self.check_time_preferences(timetable) * 20
        consecutive_class_violations = self.check_consecutive_classes(timetable) * 25
        lunch_break_violations = self.check_lunch_breaks(timetable) * 15
        
        total_violations = (faculty_conflicts + classroom_conflicts + 
                          workload_violations + time_preference_violations +
                          consecutive_class_violations + lunch_break_violations)
        
        fitness_score = max(0, fitness_score - total_violations)
        
        # Bonus for good distribution of subjects
        subject_distribution_score = self.check_subject_distribution(timetable) * 10
        fitness_score += subject_distribution_score
        
        return fitness_score
    
    def check_subject_distribution(self, timetable):
        score = 0
        for batch_id, schedule in timetable.items():
            subject_count = {}
            for day, time_slots in schedule.items():
                for time_slot, slot_data in time_slots.items():
                    if slot_data:
                        subject_id = slot_data['subject_id']
                        subject_count[subject_id] = subject_count.get(subject_id, 0) + 1
            
            # Check if subjects are evenly distributed
            subject = self.subject_map.get(list(subject_count.keys())[0] if subject_count else None)
            if subject:
                expected_classes = subject.get('classes_per_week', 3)
                for count in subject_count.values():
                    if abs(count - expected_classes) <= 1:  # Allow some flexibility
                        score += 1
        return score
    
    def run(self):
        return super().run(self.population_size, self.generations, self.mutation_rate)