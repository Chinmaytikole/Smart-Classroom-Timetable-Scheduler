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
        
        # Identify theory and lab subjects
        self.theory_subjects = [s for s in subjects if s.get('subject_type') == 'THEORY']
        self.lab_subjects = [s for s in subjects if s.get('subject_type') == 'LAB']
        
    def initialize_population(self, size):
        population = []
        for _ in range(size):
            timetable = {}
            
            # First schedule theory subjects synchronously across all batches
            timetable = self.initialize_theory_slots()
            
            # Then fill remaining slots with lab subjects
            timetable = self.fill_lab_slots(timetable)
                
            population.append(timetable)
        return population
    
    def initialize_theory_slots(self):
        """Initialize timetable with theory subjects scheduled at same time across batches"""
        timetable = {}
        
        # Create empty timetable structure
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
        
        # Schedule theory subjects synchronously
        for theory_subject in self.theory_subjects:
            required_classes = theory_subject.get('classes_per_week', 3)
            
            for _ in range(required_classes):
                # Find a time slot that's available for all batches in this department
                available_slot = self.find_available_theory_slot(timetable, theory_subject)
                
                if available_slot:
                    day, time_slot = available_slot
                    faculty_for_subject = self.get_faculty_for_subject(theory_subject['id'])
                    classroom = self.get_available_classroom('THEORY')
                    
                    # Schedule this theory subject at the same time for all batches in the department
                    for batch in self.batches:
                        if batch.get('department_id') == theory_subject.get('department_id'):
                            timetable[batch['id']][day][time_slot] = {
                                'subject_id': theory_subject['id'],
                                'faculty_id': faculty_for_subject['id'] if faculty_for_subject else None,
                                'classroom_id': classroom['id'] if classroom else None
                            }
        
        return timetable
    
    def find_available_theory_slot(self, timetable, theory_subject):
        """Find a time slot available for all batches in the same department"""
        # Get batches that need this theory subject
        target_batches = [b for b in self.batches if b.get('department_id') == theory_subject.get('department_id')]
        
        available_slots = []
        for day in self.days:
            for time_slot in self.time_slots:
                if time_slot == self.lunch_break:
                    continue
                
                # Check if slot is available for all target batches
                slot_available = True
                for batch in target_batches:
                    if timetable[batch['id']][day][time_slot] is not None:
                        slot_available = False
                        break
                
                if slot_available:
                    available_slots.append((day, time_slot))
        
        return random.choice(available_slots) if available_slots else None
    
    def fill_lab_slots(self, timetable):
        """Fill remaining slots with lab subjects independently for each batch"""
        for batch in self.batches:
            batch_id = batch['id']
            batch_lab_subjects = [s for s in self.lab_subjects if s.get('department_id') == batch.get('department_id')]
            
            for lab_subject in batch_lab_subjects:
                required_classes = lab_subject.get('classes_per_week', 3)
                scheduled_classes = self.count_scheduled_classes(timetable, batch_id, lab_subject['id'])
                
                while scheduled_classes < required_classes:
                    # Find available slot for this batch
                    available_slot = self.find_available_lab_slot(timetable, batch_id)
                    if not available_slot:
                        break
                    
                    day, time_slot = available_slot
                    faculty_for_subject = self.get_faculty_for_subject(lab_subject['id'])
                    classroom = self.get_available_classroom('LAB')
                    
                    timetable[batch_id][day][time_slot] = {
                        'subject_id': lab_subject['id'],
                        'faculty_id': faculty_for_subject['id'] if faculty_for_subject else None,
                        'classroom_id': classroom['id'] if classroom else None
                    }
                    scheduled_classes += 1
        
        return timetable
    
    def find_available_lab_slot(self, timetable, batch_id):
        """Find available slot for lab subject in a specific batch"""
        available_slots = []
        for day in self.days:
            for time_slot in self.time_slots:
                if (time_slot != self.lunch_break and 
                    timetable[batch_id][day][time_slot] is None):
                    available_slots.append((day, time_slot))
        
        return random.choice(available_slots) if available_slots else None
    
    def count_scheduled_classes(self, timetable, batch_id, subject_id):
        """Count how many times a subject is scheduled for a batch"""
        count = 0
        for day in self.days:
            for time_slot in self.time_slots:
                slot_data = timetable[batch_id][day].get(time_slot)
                if slot_data and slot_data['subject_id'] == subject_id:
                    count += 1
        return count
    
    def get_faculty_for_subject(self, subject_id):
        # Find faculty who can teach this subject
        eligible_faculty = [f for f in self.faculty if self.can_teach_subject(f, subject_id)]
        return random.choice(eligible_faculty) if eligible_faculty else None
    
    def can_teach_subject(self, faculty, subject_id):
        """Check if faculty can teach this subject based on faculty_subjects table"""
        conn = sqlite3.connect('timetable.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM faculty_subjects 
            WHERE faculty_id = ? AND subject_id = ?
        ''', (faculty['id'], subject_id))
        
        can_teach = cursor.fetchone()[0] > 0
        conn.close()
    
        return can_teach
    
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
        
        # Check for theory synchronization violations (NEW)
        theory_sync_violations = self.check_theory_synchronization(timetable)
        fitness_score -= theory_sync_violations * 100  # High penalty for sync violations
        
        return max(0, fitness_score)
    
    def check_theory_synchronization(self, timetable):
        """Check if theory subjects are scheduled at same time across batches"""
        violations = 0
        
        # Group theory subjects by department
        department_theory_slots = {}
        
        # Collect all theory subject scheduling information
        for batch_id, schedule in timetable.items():
            batch = self.batch_map[batch_id]
            dept_id = batch.get('department_id')
            
            if dept_id not in department_theory_slots:
                department_theory_slots[dept_id] = {}
            
            for day, time_slots in schedule.items():
                for time_slot, slot_data in time_slots.items():
                    if slot_data and slot_data['subject_id']:
                        subject = self.subject_map.get(slot_data['subject_id'])
                        if subject and subject['subject_type'] == 'THEORY':
                            key = (day, time_slot)
                            if key not in department_theory_slots[dept_id]:
                                department_theory_slots[dept_id][key] = set()
                            department_theory_slots[dept_id][key].add(slot_data['subject_id'])
        
        # Check for synchronization violations
        for dept_id, time_slots in department_theory_slots.items():
            for (day, time_slot), subject_ids in time_slots.items():
                # If multiple theory subjects are scheduled at same time in same department, it's a violation
                if len(subject_ids) > 1:
                    violations += len(subject_ids) - 1
        
        return violations
    
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
        """Enhanced crossover that creates two children"""
        # Create two children
        child1 = deepcopy(parent1)
        child2 = deepcopy(parent2)

        # Single-point crossover for both children
        crossover_point = random.randint(1, len(self.days) - 1)
        crossover_days = self.days[crossover_point:]

        # First child: parent1 with some days from parent2
        for batch_id in parent2:
            if batch_id not in child1:
                child1[batch_id] = {}
            for day in crossover_days:
                if day in parent2[batch_id]:
                    child1[batch_id][day] = deepcopy(parent2[batch_id][day])

        # Second child: parent2 with some days from parent1
        for batch_id in parent1:
            if batch_id not in child2:
                child2[batch_id] = {}
            for day in crossover_days:
                if day in parent1[batch_id]:
                    child2[batch_id][day] = deepcopy(parent1[batch_id][day])
                    
        return child1, child2
    
    def mutate(self, timetable):
        mutated = deepcopy(timetable)
        
        # Don't mutate theory subjects to maintain synchronization
        # Only mutate lab subjects
        lab_slots = []
        for batch_id in mutated:
            for day in self.days:
                for time_slot in self.time_slots:
                    if time_slot == self.lunch_break:
                        continue
                    slot_data = mutated[batch_id][day][time_slot]
                    if slot_data:
                        subject = self.subject_map.get(slot_data['subject_id'])
                        if subject and subject['subject_type'] == 'LAB':
                            lab_slots.append((batch_id, day, time_slot))
        
        if not lab_slots:
            return mutated
            
        batch_id, day, time_slot = random.choice(lab_slots)
        
        if random.random() < 0.5:  # 50% chance to change lab subject
            batch = self.batch_map[batch_id]
            lab_subjects = [s for s in self.lab_subjects if s.get('department_id') == batch.get('department_id')]
            if lab_subjects:
                new_subject = random.choice(lab_subjects)
                faculty_for_subject = self.get_faculty_for_subject(new_subject['id'])
                if faculty_for_subject:
                    classroom = self.get_available_classroom('LAB')
                    mutated[batch_id][day][time_slot] = {
                        'subject_id': new_subject['id'],
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
                child1, child2 = self.crossover(parent1, parent2)
                
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

# Enhanced version with same class name but different functionality
class EnhancedGeneticTimetable(GeneticTimetable):
    def __init__(self, subjects, faculty, classrooms, batches, constraints):
        # Convert sqlite3.Row objects to dictionaries if needed
        if subjects and hasattr(subjects[0], '_fields'):  # If it's sqlite3.Row
            subjects = [dict(subj) for subj in subjects]
        if faculty and hasattr(faculty[0], '_fields'):
            faculty = [dict(fac) for fac in faculty]
        if classrooms and hasattr(classrooms[0], '_fields'):
            classrooms = [dict(room) for room in classrooms]
        if batches and hasattr(batches[0], '_fields'):
            batches = [dict(batch) for batch in batches]
            
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
        theory_sync_violations = self.check_theory_synchronization(timetable) * 100  # High penalty for sync violations
        
        total_violations = (faculty_conflicts + classroom_conflicts + 
                          workload_violations + time_preference_violations +
                          consecutive_class_violations + lunch_break_violations +
                          subject_distribution_violations + max_classes_violations +
                          fixed_slots_violations + faculty_availability_violations +
                          theory_sync_violations)
        
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

    def tournament_selection(self, population, fitness_scores, tournament_size=3):
        """Tournament selection"""
        tournament_indices = random.sample(range(len(population)), tournament_size)
        tournament = [(population[i], fitness_scores[i]) for i in tournament_indices]
        return max(tournament, key=lambda x: x[1])[0]