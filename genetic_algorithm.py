# genetic_algorithm.py
import random
import numpy as np
from copy import deepcopy
import sqlite3

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

# genetic_algorithm.py
import random
import numpy as np
from copy import deepcopy
import sqlite3
from datetime import datetime

class EnhancedGeneticTimetable(GeneticTimetable):
    def __init__(self, subjects, faculty, classrooms, batches, constraints):
        super().__init__(subjects, faculty, classrooms, batches, constraints)
        self.population_size = 200
        self.generations = 1000
        self.mutation_rate = 0.15
        self.crossover_rate = 0.85
        self.elitism_rate = 0.1
        
        # Additional constraints
        self.max_classes_per_day_per_batch = constraints.get('max_classes_per_day_per_batch', 6)
        self.fixed_slots = constraints.get('fixed_slots', {})
        self.faculty_leaves = self.load_faculty_leaves()
        
    def load_faculty_leaves(self):
        """Load faculty leave information from database"""
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT faculty_id, avg_leaves_per_month FROM faculty_leaves')
        leaves_data = cursor.fetchall()
        
        faculty_leaves = {}
        for faculty_id, avg_leaves in leaves_data:
            faculty_leaves[faculty_id] = avg_leaves
            
        conn.close()
        return faculty_leaves
    
    def calculate_fitness(self, timetable):
        fitness_score = 1000  # Start with perfect score
        
        # Weight different constraint violations
        faculty_conflicts = self.check_faculty_conflicts(timetable) * 50
        classroom_conflicts = self.check_classroom_conflicts(timetable) * 50
        workload_violations = self.check_workload_violations(timetable) * 30
        time_preference_violations = self.check_time_preferences(timetable) * 20
        consecutive_class_violations = self.check_consecutive_classes(timetable) * 25
        lunch_break_violations = self.check_lunch_breaks(timetable) * 15
        
        # New constraint violations
        subject_distribution_violations = self.check_subject_distribution(timetable) * 40
        max_classes_violations = self.check_max_classes_per_day(timetable) * 35
        fixed_slots_violations = self.check_fixed_slots(timetable) * 60
        faculty_availability_violations = self.check_faculty_availability(timetable) * 25
        
        total_violations = (faculty_conflicts + classroom_conflicts + 
                          workload_violations + time_preference_violations +
                          consecutive_class_violations + lunch_break_violations +
                          subject_distribution_violations + max_classes_violations +
                          fixed_slots_violations + faculty_availability_violations)
        
        fitness_score = max(0, fitness_score - total_violations)
        
        return fitness_score
    
    def check_subject_distribution(self, timetable):
        """Check if subjects have correct number of classes per week"""
        violations = 0
        
        for batch_id, schedule in timetable.items():
            subject_count = {}
            
            # Count classes for each subject
            for day, time_slots in schedule.items():
                for time_slot, slot_data in time_slots.items():
                    if slot_data:
                        subject_id = slot_data['subject_id']
                        subject_count[subject_id] = subject_count.get(subject_id, 0) + 1
            
            # Check against required classes per week
            for subject_id, actual_count in subject_count.items():
                subject = self.subject_map.get(subject_id)
                if subject:
                    required_count = subject.get('classes_per_week', 3)
                    if actual_count != required_count:
                        violations += abs(actual_count - required_count)
        
        return violations
    
    def check_max_classes_per_day(self, timetable):
        """Check maximum classes per day per batch constraint"""
        violations = 0
        
        for batch_id, schedule in timetable.items():
            for day, time_slots in schedule.items():
                class_count = sum(1 for time_slot, slot_data in time_slots.items() 
                                if slot_data and time_slot != self.lunch_break)
                
                if class_count > self.max_classes_per_day_per_batch:
                    violations += (class_count - self.max_classes_per_day_per_batch)
        
        return violations
    
    def check_fixed_slots(self, timetable):
        """Check if fixed slots are respected"""
        violations = 0
        
        for fixed_slot in self.fixed_slots:
            batch_id = fixed_slot['batch_id']
            day = fixed_slot['day']
            time_slot = fixed_slot['time_slot']
            required_subject_id = fixed_slot['subject_id']
            required_faculty_id = fixed_slot.get('faculty_id')
            required_classroom_id = fixed_slot.get('classroom_id')
            
            if batch_id in timetable and day in timetable[batch_id]:
                actual_slot = timetable[batch_id][day].get(time_slot)
                
                if not actual_slot:
                    violations += 1  # Slot is empty but should be fixed
                else:
                    if actual_slot['subject_id'] != required_subject_id:
                        violations += 1
                    if required_faculty_id and actual_slot['faculty_id'] != required_faculty_id:
                        violations += 1
                    if required_classroom_id and actual_slot['classroom_id'] != required_classroom_id:
                        violations += 1
        
        return violations
    
    def check_faculty_availability(self, timetable):
        """Check faculty availability considering leaves"""
        violations = 0
        faculty_workload = {f['id']: 0 for f in self.faculty}
        
        # Count faculty workload
        for batch_id, schedule in timetable.items():
            for day, time_slots in schedule.items():
                for time_slot, slot_data in time_slots.items():
                    if slot_data and slot_data['faculty_id']:
                        faculty_id = slot_data['faculty_id']
                        faculty_workload[faculty_id] += 1
        
        # Check against availability considering leaves
        for faculty_id, workload in faculty_workload.items():
            avg_leaves = self.faculty_leaves.get(faculty_id, 0)
            available_days = len(self.days) * (20 - avg_leaves) / 30  # Approximate available days
            
            max_allowed_hours = self.faculty_map[faculty_id].get('max_hours_per_day', 8) * available_days
            
            if workload > max_allowed_hours:
                violations += (workload - max_allowed_hours)
        
        return violations
    
    def initialize_population(self, size):
        """Initialize population with fixed slots already assigned"""
        population = []
        
        for _ in range(size):
            timetable = {}
            
            # Initialize empty timetable structure
            for batch in self.batches:
                batch_id = batch['id']
                timetable[batch_id] = {}
                for day in self.days:
                    timetable[batch_id][day] = {}
                    for time_slot in self.time_slots:
                        if time_slot == self.lunch_break:
                            timetable[batch_id][day][time_slot] = None
                        else:
                            timetable[batch_id][day][time_slot] = None
            
            # Assign fixed slots first
            for fixed_slot in self.fixed_slots:
                batch_id = fixed_slot['batch_id']
                day = fixed_slot['day']
                time_slot = fixed_slot['time_slot']
                
                if (batch_id in timetable and day in timetable[batch_id] and 
                    time_slot in timetable[batch_id][day]):
                    
                    timetable[batch_id][day][time_slot] = {
                        'subject_id': fixed_slot['subject_id'],
                        'faculty_id': fixed_slot.get('faculty_id'),
                        'classroom_id': fixed_slot.get('classroom_id')
                    }
            
            # Fill remaining slots
            for batch in self.batches:
                batch_id = batch['id']
                
                # Get subjects for this batch
                batch_subjects = [s for s in self.subjects if s.get('department_id') == batch.get('department_id')]
                
                for day in self.days:
                    for time_slot in self.time_slots:
                        # Skip if already filled with fixed slot or lunch break
                        if (timetable[batch_id][day][time_slot] is not None or 
                            time_slot == self.lunch_break):
                            continue
                        
                        # Try to assign a subject that hasn't reached its weekly limit
                        available_subjects = []
                        for subject in batch_subjects:
                            # Count how many times this subject is already scheduled this week
                            weekly_count = self.count_subject_weekly(timetable, batch_id, subject['id'])
                            if weekly_count < subject.get('classes_per_week', 3):
                                available_subjects.append(subject)
                        
                        if available_subjects:
                            subject = random.choice(available_subjects)
                            faculty_for_subject = self.get_faculty_for_subject(subject['id'])
                            
                            if faculty_for_subject:
                                classroom = self.get_available_classroom(subject['subject_type'])
                                timetable[batch_id][day][time_slot] = {
                                    'subject_id': subject['id'],
                                    'faculty_id': faculty_for_subject['id'],
                                    'classroom_id': classroom['id'] if classroom else None
                                }
            
            population.append(timetable)
        
        return population
    
    def count_subject_weekly(self, timetable, batch_id, subject_id):
        """Count how many times a subject is scheduled in a week for a batch"""
        count = 0
        if batch_id in timetable:
            for day in self.days:
                for time_slot in self.time_slots:
                    slot_data = timetable[batch_id][day].get(time_slot)
                    if slot_data and slot_data['subject_id'] == subject_id:
                        count += 1
        return count
    
    def mutate(self, timetable):
        """Enhanced mutation that respects constraints"""
        mutated = deepcopy(timetable)
        
        # Don't mutate fixed slots
        non_fixed_slots = []
        for batch_id in mutated:
            for day in self.days:
                for time_slot in self.time_slots:
                    if (time_slot != self.lunch_break and 
                        not self.is_fixed_slot(batch_id, day, time_slot)):
                        non_fixed_slots.append((batch_id, day, time_slot))
        
        if not non_fixed_slots:
            return mutated
        
        # Select a random non-fixed slot to mutate
        batch_id, day, time_slot = random.choice(non_fixed_slots)
        
        if random.random() < 0.7:  # 70% chance to change subject
            # Get current subject and find alternatives
            current_slot = mutated[batch_id][day][time_slot]
            current_subject_id = current_slot['subject_id'] if current_slot else None
            
            # Find subjects that haven't reached their weekly limit
            available_subjects = []
            for subject in self.subjects:
                if subject.get('department_id') == self.batch_map[batch_id].get('department_id'):
                    weekly_count = self.count_subject_weekly(mutated, batch_id, subject['id'])
                    if weekly_count < subject.get('classes_per_week', 3):
                        available_subjects.append(subject)
            
            if available_subjects:
                new_subject = random.choice(available_subjects)
                faculty_for_subject = self.get_faculty_for_subject(new_subject['id'])
                
                if faculty_for_subject:
                    classroom = self.get_available_classroom(new_subject['subject_type'])
                    mutated[batch_id][day][time_slot] = {
                        'subject_id': new_subject['id'],
                        'faculty_id': faculty_for_subject['id'],
                        'classroom_id': classroom['id'] if classroom else None
                    }
        else:  # 30% chance to clear the slot
            mutated[batch_id][day][time_slot] = None
            
        return mutated
    
    def is_fixed_slot(self, batch_id, day, time_slot):
        """Check if a slot is fixed"""
        for fixed_slot in self.fixed_slots:
            if (fixed_slot['batch_id'] == batch_id and 
                fixed_slot['day'] == day and 
                fixed_slot['time_slot'] == time_slot):
                return True
        return False
    
    def run(self):
        """Run the enhanced genetic algorithm"""
        population = self.initialize_population(self.population_size)
        best_fitness = -1
        best_timetable = None
        
        for generation in range(self.generations):
            # Evaluate fitness
            fitness_scores = [self.calculate_fitness(timetable) for timetable in population]
            
            # Find best timetable
            max_fitness = max(fitness_scores)
            if max_fitness > best_fitness:
                best_fitness = max_fitness
                best_timetable = population[fitness_scores.index(max_fitness)]
                
            # Elitism: keep best individuals
            elite_size = int(self.population_size * self.elitism_rate)
            elite_indices = np.argsort(fitness_scores)[-elite_size:]
            new_population = [population[i] for i in elite_indices]
            
            # Create new generation
            while len(new_population) < self.population_size:
                # Tournament selection
                parent1 = self.tournament_selection(population, fitness_scores)
                parent2 = self.tournament_selection(population, fitness_scores)
                
                # Crossover
                if random.random() < self.crossover_rate:
                    child1, child2 = self.crossover(parent1, parent2)
                else:
                    child1, child2 = parent1, parent2
                
                # Mutation
                if random.random() < self.mutation_rate:
                    child1 = self.mutate(child1)
                if random.random() < self.mutation_rate:
                    child2 = self.mutate(child2)
                
                new_population.extend([child1, child2])
            
            population = new_population[:self.population_size]
            
            # Print progress
            if generation % 50 == 0:
                print(f"Generation {generation}: Best Fitness = {best_fitness}")
                
        return best_timetable, best_fitness
    
    def tournament_selection(self, population, fitness_scores, tournament_size=3):
        """Tournament selection"""
        tournament_indices = random.sample(range(len(population)), tournament_size)
        tournament = [(population[i], fitness_scores[i]) for i in tournament_indices]
        return max(tournament, key=lambda x: x[1])[0]