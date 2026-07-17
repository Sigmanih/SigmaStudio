import math

class ScientificCalculator:
    def __init__(self):
        self.history = []
        # Sandbox setup per sicurezza
        allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith('_')}
        allowed_names['e'] = 2.718281828459045
        allowed_names['pi'] = 3.141592653589793
    
    def calculate(self, expression):
        try:
            expr_safe = str(expression).replace('^', '**')
            # Valutazione sicura con namespace ristretto
            result = eval(expr_safe, {'__builtins__': {}}, allowed_names)
            
            if isinstance(result, complex):
                raise ValueError('Complex number not supported.')
                
            res_float = float(result)
            self.history.append((expression.strip(), res_float))
            return res_float
            
        except ZeroDivisionError:
            raise ValueError('Zero division error')
        except Exception as e:
            # Uso di single quotes per evitare conflitti con il JSON esterno
            raise ValueError(f'Calculation Error: {str(e)}')

    def get_history(self):
        return self.history[-5:] if hasattr(self, 'history') else []

if __name__ == '__main__':
    calc = ScientificCalculator()
    print('Scientific Calculator Ready.')
