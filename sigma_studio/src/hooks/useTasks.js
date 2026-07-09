import { useState, useCallback } from 'react';

// ==============================================================================
// useTasks Hook | Fetch, save, toggle, delete tasks
// ==============================================================================

export function useTasks() {
  const [tasks, setTasks] = useState([]);

  const fetchTasks = useCallback(async () => {
    try {
      const res = await fetch('/api/tasks');
      const data = await res.json();
      setTasks(data || []);
    } catch (e) {
      console.error("Fetch tasks error:", e);
    }
  }, []);

  const saveTasks = useCallback(async (newTasks) => {
    try {
      const res = await fetch('/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newTasks)
      });
      return (await res.json()).success;
    } catch (e) {
      console.error("Save tasks error:", e);
      return false;
    }
  }, []);

  const handleTaskSave = useCallback(async (taskData, editingTask) => {
    let newTasks;
    if (editingTask) {
      newTasks = tasks.map(t => t.id === editingTask.id ? taskData : t);
    } else {
      newTasks = [...tasks, { ...taskData, id: Date.now() }];
    }
    setTasks(newTasks);
    return await saveTasks(newTasks);
  }, [tasks, saveTasks]);

  const toggleTaskStatus = useCallback(async (task) => {
    const newStatus = task.status === 'done' ? 'in_corso' : 'done';
    const newTasks = tasks.map(t => t.id === task.id ? { ...t, status: newStatus } : t);
    setTasks(newTasks);
    await saveTasks(newTasks);
  }, [tasks, saveTasks]);

  const deleteTask = useCallback(async (taskTitle) => {
    const newTasks = tasks.filter(t => t.titolo !== taskTitle);
    setTasks(newTasks);
    await saveTasks(newTasks);
  }, [tasks, saveTasks]);

  const clearAllTasks = useCallback(async () => {
    setTasks([]);
    await saveTasks([]);
  }, [saveTasks]);

  return { tasks, setTasks, fetchTasks, handleTaskSave, toggleTaskStatus, deleteTask, clearAllTasks };
}