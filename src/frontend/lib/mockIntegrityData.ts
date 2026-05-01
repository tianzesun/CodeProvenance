export const trendData = [
  { week: 'Jan 8', cases: 12, high: 4 },
  { week: 'Jan 15', cases: 18, high: 6 },
  { week: 'Jan 22', cases: 14, high: 5 },
  { week: 'Jan 29', cases: 25, high: 9 },
  { week: 'Feb 5', cases: 21, high: 7 },
  { week: 'Feb 12', cases: 32, high: 11 },
  { week: 'Feb 19', cases: 28, high: 10 },
];

export const courseData = [
  { code: 'CSC108', name: 'Intro to Computer Programming', students: 412, assignments: 6, flagged: 9 },
  { code: 'CSC148', name: 'Data Structures', students: 286, assignments: 5, flagged: 14 },
  { code: 'CSC207', name: 'Software Design', students: 174, assignments: 4, flagged: 5 },
  { code: 'MAT244', name: 'Applied Algorithms', students: 138, assignments: 3, flagged: 3 },
  { code: 'CSC369', name: 'Operating Systems', students: 96, assignments: 4, flagged: 7 },
  { code: 'CSC384', name: 'AI Fundamentals', students: 152, assignments: 5, flagged: 4 },
];

export const assignmentCases = [
  {
    rank: 1,
    id: 'case-001',
    course: 'CSC108',
    assignment: 'A2 Recursion',
    students: 'Maya Chen vs Lucas Park',
    risk: 97,
    confidence: 'High',
    status: 'New',
    reason: 'Same recursive decomposition with renamed variables',
    reviewer: 'Dr. Rivera',
  },
  {
    rank: 2,
    id: 'case-002',
    course: 'CSC148',
    assignment: 'BST Lab',
    students: 'Ari Singh vs Noor Ahmed',
    risk: 94,
    confidence: 'High',
    status: 'Marked',
    reason: 'Identical edge-case logic and branch order',
    reviewer: 'TA Morgan',
  },
  {
    rank: 3,
    id: 'case-003',
    course: 'CSC207',
    assignment: 'Design Patterns',
    students: 'Elena Rossi vs Theo Grant',
    risk: 88,
    confidence: 'Medium',
    status: 'New',
    reason: 'Uncommon class structure and copied comments',
    reviewer: 'Unassigned',
  },
  {
    rank: 4,
    id: 'case-004',
    course: 'CSC369',
    assignment: 'Shell',
    students: 'Priya Shah vs Daniel Kim',
    risk: 76,
    confidence: 'Medium',
    status: 'Reviewed',
    reason: 'Similar parsing strategy after starter code removal',
    reviewer: 'Dr. Lee',
  },
  {
    rank: 5,
    id: 'case-005',
    course: 'CSC384',
    assignment: 'Search Agent',
    students: 'Sam Taylor vs June Wu',
    risk: 64,
    confidence: 'Medium',
    status: 'New',
    reason: 'Shared heuristic ordering and matching fallback logic',
    reviewer: 'TA Morgan',
  },
];

export const analyticsByCourse = [
  { course: 'CSC108', cases: 18 },
  { course: 'CSC148', cases: 24 },
  { course: 'CSC207', cases: 11 },
  { course: 'CSC369', cases: 15 },
  { course: 'CSC384', cases: 9 },
];

export const semesterRiskData = [
  { semester: 'Fall 2024', high: 28, medium: 44 },
  { semester: 'Winter 2025', high: 35, medium: 51 },
  { semester: 'Fall 2025', high: 31, medium: 47 },
  { semester: 'Winter 2026', high: 42, medium: 63 },
];

export const repeatOffenderData = [
  { label: 'First case', value: 71 },
  { label: 'Prior warning', value: 18 },
  { label: 'Repeat pattern', value: 11 },
];

export const generatedSuspicionData = [
  { month: 'Sep', cases: 8 },
  { month: 'Oct', cases: 13 },
  { month: 'Nov', cases: 17 },
  { month: 'Dec', cases: 15 },
  { month: 'Jan', cases: 19 },
  { month: 'Feb', cases: 24 },
];

export const studentACode = `def tree_score(node):
    if node is None:
        return 0

    left_total = tree_score(node.left)
    right_total = tree_score(node.right)

    if node.value < 0:
        return max(left_total, right_total)

    if left_total > right_total:
        return left_total + node.value

    return right_total + node.value`;

export const studentBCode = `def calculate_tree(current):
    if current is None:
        return 0

    first_branch = calculate_tree(current.left)
    second_branch = calculate_tree(current.right)

    if current.value < 0:
        return max(first_branch, second_branch)

    if first_branch > second_branch:
        return first_branch + current.value

    return second_branch + current.value`;
